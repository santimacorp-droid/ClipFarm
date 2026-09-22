"""
Watermark & Auto-Captions Processor
Standalone module to transcribe clips with faster-whisper and burn in clean captions + logo watermarks using FFmpeg.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from .caption_styles import ViralCaptionGenerator, CAPTION_STYLES
from .ffmpeg_utils import get_ffmpeg_path

logger = logging.getLogger(__name__)


def get_watermark_overlay_expr(position: str = "bottom_right", margin: int = 24) -> str:
    """
    Calculate the FFmpeg overlay coordinates expression for the specified corner.
    
    Args:
        position: bottom_right, bottom_left, top_right, or top_left
        margin: Margin in pixels from frame edge
        
    Returns:
        FFmpeg overlay expression (e.g. main_w-overlay_w-24:main_h-overlay_h-24)
    """
    pos = (position or "bottom_right").lower().replace("-", "_")
    m = max(0, int(margin))
    
    if pos in ["bottom_left", "bl"]:
        return f"{m}:main_h-overlay_h-{m}"
    elif pos in ["top_right", "tr"]:
        return f"main_w-overlay_w-{m}:{m}"
    elif pos in ["top_left", "tl"]:
        return f"{m}:{m}"
    elif pos in ["bottom_center", "bc", "lower_center", "lc", "center_bottom"]:
        return f"(main_w-overlay_w)/2:main_h-overlay_h-{m}"
    elif pos in ["center", "middle"]:
        return f"(main_w-overlay_w)/2:(main_h-overlay_h)/2"
    else:  # default bottom_right
        return f"main_w-overlay_w-{m}:main_h-overlay_h-{m}"


def transcribe_clip_subtitles(
    clip_path: Path,
    output_srt: Optional[Path] = None,
    language: Optional[str] = None,
    model_name: str = "base"
) -> Path:
    """
    Transcribe a single clip using faster-whisper and output an SRT file.
    
    Args:
        clip_path: Path to the video clip MP4
        output_srt: Destination SRT path (default: <clip_path_stem>.srt)
        language: Language code (e.g. en, auto)
        model_name: faster-whisper model (base, small, medium)
        
    Returns:
        Path to the generated SRT file
    """
    from faster_whisper import WhisperModel
    
    if output_srt is None:
        output_srt = clip_path.parent / f"{clip_path.stem}.srt"
    
    logger.info(f"Transcribing clip audio: {clip_path.name} (model: {model_name})")
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    
    lang_param = None if (not language or language.lower() in ["auto", "none"]) else language.split("-")[0]
    seg_iter, info = model.transcribe(str(clip_path), language=lang_param, vad_filter=True, word_timestamps=True)
    segments = list(seg_iter)
    
    if not segments:
        # Retry with vad_filter=False if no segments found
        logger.info("VAD filtered all speech, retrying without VAD filter...")
        seg_iter, _ = model.transcribe(str(clip_path), language=lang_param, vad_filter=False, word_timestamps=True)
        segments = list(seg_iter)

    from .speech_recognizer import SpeechRecognizer
    tight_srt = SpeechRecognizer._words_to_tight_srt(segments)
    
    if not tight_srt.strip():
        tight_srt = "1\n00:00:00,000 --> 00:00:05,000\n\n"

    output_srt.parent.mkdir(parents=True, exist_ok=True)
    output_srt.write_text(tight_srt, encoding="utf-8")
    logger.info(f"Generated clip transcript: {output_srt} ({len(segments)} segments)")
    return output_srt


def process_clip_watermark_and_captions(
    input_clip: Path,
    output_clip: Path,
    watermark_path: Optional[Path] = None,
    srt_path: Optional[Path] = None,
    ass_path: Optional[Path] = None,
    position: str = "bottom_right",
    scale_percent: float = 15.0,
    opacity: float = 0.85,
    margin: int = 24,
    caption_style: str = "clean_box",
    hook_title: Optional[str] = None,
    show_hook_banner: bool = False
) -> Path:
    """
    Process a video clip by burning subtitles and overlaying a watermark in a single FFmpeg pass.
    
    Args:
        input_clip: Input video file path
        output_clip: Destination output video file path
        watermark_path: Path to PNG/logo image (optional)
        srt_path: Path to SRT subtitle file (optional)
        ass_path: Path to pre-generated ASS subtitle file (optional)
        position: Corner position (bottom_right, bottom_left, top_right, top_left)
        scale_percent: Watermark width relative to video width (e.g. 15 for 15%)
        opacity: Watermark opacity (0.05 to 1.0)
        margin: Padding from frame edge in pixels
        caption_style: Subtitle style (clean_box, hormozi_yellow, neon_green, neon_cyan, none)
        hook_title: Optional headline hook title to show at the top
        show_hook_banner: Whether to render the top hook banner
        
    Returns:
        Path to the finished output video
    """
    ffmpeg_bin = get_ffmpeg_path()
    output_clip.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Prepare ASS subtitle file if captions are requested
    final_ass: Optional[Path] = None
    if caption_style and caption_style != "none":
        if ass_path and ass_path.exists():
            final_ass = ass_path
        elif srt_path and srt_path.exists():
            ass_target = output_clip.parent / f"{output_clip.stem}.ass"
            try:
                ViralCaptionGenerator.generate_clip_ass(
                    srt_path=srt_path,
                    output_ass_path=ass_target,
                    clip_start_seconds=0.0,
                    clip_end_seconds=999999.0,
                    style=caption_style,
                    hook_title=hook_title if show_hook_banner else None
                )
                if ass_target.exists():
                    final_ass = ass_target
            except Exception as e:
                logger.error(f"Failed to generate ASS from SRT: {e}")

    has_watermark = watermark_path is not None and watermark_path.exists()
    has_subtitles = final_ass is not None and final_ass.exists()

    logger.info(f"Processing clip: {input_clip.name} -> {output_clip.name} (Watermark: {has_watermark}, Captions: {has_subtitles})")

    # 2. Build FFmpeg command based on active features
    if has_watermark and has_subtitles:
        # Combined single-pass filter graph
        scale_ratio = max(0.05, min(0.50, float(scale_percent) / 100.0))
        op_val = max(0.05, min(1.0, float(opacity)))
        overlay_expr = get_watermark_overlay_expr(position, margin)
        escaped_ass = str(final_ass.resolve()).replace("'", "\'")

        filter_graph = (
            f"[1:v]format=rgba,colorchannelmixer=aa={op_val}[wm_alpha];"
            f"[wm_alpha][0:v]scale2ref=w=main_w*{scale_ratio}:h=ow/mdar[wm_scaled][base_v];"
            f"[base_v][wm_scaled]overlay={overlay_expr}[v_wm];"
            f"[v_wm]ass='{escaped_ass}'[outv]"
        )

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(input_clip),
            "-i", str(watermark_path),
            "-filter_complex", filter_graph,
            "-map", "[outv]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_clip)
        ]

    elif has_watermark and not has_subtitles:
        # Watermark only
        scale_ratio = max(0.05, min(0.50, float(scale_percent) / 100.0))
        op_val = max(0.05, min(1.0, float(opacity)))
        overlay_expr = get_watermark_overlay_expr(position, margin)

        filter_graph = (
            f"[1:v]format=rgba,colorchannelmixer=aa={op_val}[wm_alpha];"
            f"[wm_alpha][0:v]scale2ref=w=main_w*{scale_ratio}:h=ow/mdar[wm_scaled][base_v];"
            f"[base_v][wm_scaled]overlay={overlay_expr}[outv]"
        )

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(input_clip),
            "-i", str(watermark_path),
            "-filter_complex", filter_graph,
            "-map", "[outv]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_clip)
        ]

    elif not has_watermark and has_subtitles:
        # Subtitles only
        escaped_ass = str(final_ass.resolve()).replace("'", "\'")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(input_clip),
            "-vf", f"ass='{escaped_ass}'",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_clip)
        ]

    else:
        # Clean copy / re-encode
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(input_clip),
            "-c:v", "copy",
            "-c:a", "copy",
            str(output_clip)
        ]

    # 3. Execute FFmpeg
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0 or not output_clip.exists() or output_clip.stat().st_size <= 1024:
        logger.error(f"FFmpeg post-processing failed: {result.stderr}")
        raise RuntimeError(f"FFmpeg post-processing failed: {result.stderr[:300]}")

    logger.info(f"Successfully processed output clip: {output_clip} ({output_clip.stat().st_size} bytes)")
    return output_clip


def transcribe_and_process_clip(
    clip_path: Path,
    output_path: Path,
    watermark_path: Optional[Path] = None,
    position: str = "bottom_right",
    scale_percent: float = 15.0,
    opacity: float = 0.85,
    margin: int = 24,
    caption_style: str = "clean_box",
    language: Optional[str] = "en"
) -> Path:
    """
    One-stop function: Transcribes a finished clip using faster-whisper and burns captions + watermark.
    """
    temp_srt = clip_path.parent / f"{clip_path.stem}_auto.srt"
    transcribe_clip_subtitles(clip_path, output_srt=temp_srt, language=language)
    
    return process_clip_watermark_and_captions(
        input_clip=clip_path,
        output_clip=output_path,
        watermark_path=watermark_path,
        srt_path=temp_srt,
        position=position,
        scale_percent=scale_percent,
        opacity=opacity,
        margin=margin,
        caption_style=caption_style
    )


def render_text_watermark(
    text: str,
    output_path: Optional[Path] = None,
    font_size: int = 34,
    opacity: float = 0.50,
    text_color: Tuple[int, int, int] = (255, 255, 255),
    shadow_color: Tuple[int, int, int] = (0, 0, 0),
    padding: int = 12
) -> Any:
    """
    Renders a semi-transparent text/handle watermark (e.g. '@yourhandle', '@creator')
    with a subtle drop shadow for clear visibility over both light and dark video frames.
    
    Args:
        text: Handle or watermark text (e.g. '@yourhandle')
        output_path: Optional path to save PNG file
        font_size: Font size in pixels
        opacity: Opacity from 0.05 to 1.0 (default 0.50)
        text_color: RGB tuple for main text (default white)
        shadow_color: RGB tuple for shadow
        padding: Padding around text in pixels
        
    Returns:
        PIL Image instance of the rendered watermark
    """
    from PIL import Image, ImageDraw, ImageFont

    clean_text = str(text or "").strip()
    if not clean_text:
        clean_text = "@clip"

    # Resolve system fonts
    font = None
    for font_p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.exists(font_p):
            try:
                font = ImageFont.truetype(font_p, font_size)
                break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    d_draw = ImageDraw.Draw(dummy)

    text_w = d_draw.textlength(clean_text, font=font)
    text_h = int(font_size * 1.25)

    img_w = int(text_w + padding * 2)
    img_h = int(text_h + padding * 2)

    wm_img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wm_img)

    alpha_val = int(max(0.05, min(1.0, float(opacity))) * 255)
    shadow_alpha = int(alpha_val * 0.75)

    tx = padding
    ty = padding

    # Draw subtle dark drop-shadow offset by 2px
    draw.text((tx + 2, ty + 2), clean_text, font=font, fill=(shadow_color[0], shadow_color[1], shadow_color[2], shadow_alpha))
    draw.text((tx + 1, ty + 1), clean_text, font=font, fill=(shadow_color[0], shadow_color[1], shadow_color[2], shadow_alpha))

    # Draw main text
    draw.text((tx, ty), clean_text, font=font, fill=(text_color[0], text_color[1], text_color[2], alpha_val))

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        wm_img.save(out_p, "PNG")

    return wm_img
