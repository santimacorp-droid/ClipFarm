"""
Full video editing for Campaign Mode (full_video_edit mode).

Pipeline:
  source.mp4
    → remove_dead_air()      : trim silence gaps > 1.2s (keeps 0.4s)
    → generate_outro_card()  : 2.5s branded end card (optional)
    → append_outro()         : concat main + outro
    → Result: single edited clip, no submoment extraction
"""
import subprocess
import logging
import re
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


def detect_silence_gaps(
    video_path:    Path,
    threshold_db:  float = -40.0,
    min_gap_sec:   float = 1.2
) -> List[Dict[str, float]]:
    """
    Use FFmpeg silencedetect to find silence gaps in the audio.
    Returns list of {start, end, duration} dicts.
    """
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_gap_sec}",
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        stderr = result.stderr

        gaps = []
        starts = re.findall(r'silence_start:\s*([0-9.]+)', stderr)
        ends   = re.findall(r'silence_end:\s*([0-9.]+)', stderr)

        for s, e in zip(starts, ends):
            start_f = float(s)
            end_f   = float(e)
            if end_f > start_f:
                gaps.append({
                    'start':    start_f,
                    'end':      end_f,
                    'duration': end_f - start_f
                })

        logger.info(f"detect_silence_gaps: found {len(gaps)} gap(s) in {video_path.name}")
        return gaps

    except Exception as e:
        logger.warning(f"detect_silence_gaps failed: {e}")
        return []


def get_video_duration(video_path: Path) -> float:
    """Return video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, timeout=30
        )
        val = result.stdout.strip()
        return float(val) if val else 0.0
    except Exception:
        return 0.0


def has_audio_stream(video_path: Path) -> bool:
    """Check if video file contains an audio stream."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_path)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return "audio" in r.stdout.lower()
    except Exception:
        return False


def remove_dead_air(
    input_path:   Path,
    output_path:  Path,
    threshold_db: float = -40.0,
    min_gap_sec:  float = 1.2,
    keep_sec:     float = 0.4
) -> bool:
    """
    Remove silence gaps > min_gap_sec, keeping keep_sec of natural pause at each gap.

    Strategy:
    1. Detect silence gaps
    2. Build a list of "keep" segments (the non-silent parts + keep_sec buffer)
    3. Re-encode / trim per segment
    4. Concat all segments with faststart
    """
    total_dur = get_video_duration(input_path)
    if total_dur <= 0:
        logger.warning(f"remove_dead_air: could not determine duration of {input_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(input_path), str(output_path))
        return True

    gaps = detect_silence_gaps(input_path, threshold_db, min_gap_sec)

    if not gaps:
        logger.info("remove_dead_air: no silence gaps found, copying as-is")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(input_path), str(output_path))
        return True

    # Build keep segments: everything EXCEPT the interior of each gap
    half_keep = keep_sec / 2.0
    keep_segments = []
    cursor = 0.0

    for gap in gaps:
        seg_end = gap['start'] + half_keep
        if seg_end > cursor:
            keep_segments.append({'start': cursor, 'end': seg_end})
        cursor = gap['end'] - half_keep
        if cursor < 0:
            cursor = 0.0

    # Final segment to end of video
    if cursor < total_dur:
        keep_segments.append({'start': cursor, 'end': total_dur})

    logger.info(f"remove_dead_air: keeping {len(keep_segments)} segment(s), "
                f"removed {len(gaps)} gap(s)")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(keep_segments) <= 1:
        shutil.copy2(str(input_path), str(output_path))
        return True

    with tempfile.TemporaryDirectory() as tmp:
        segment_files = []

        for i, seg in enumerate(keep_segments):
            seg_path = Path(tmp) / f"seg_{i:04d}.mp4"
            duration = seg['end'] - seg['start']
            if duration < 0.1:
                continue

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(seg['start']),
                "-i", str(input_path),
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                str(seg_path)
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and seg_path.exists() and seg_path.stat().st_size > 0:
                segment_files.append(seg_path)

        if not segment_files:
            logger.error("remove_dead_air: no segments produced, fallback to original")
            shutil.copy2(str(input_path), str(output_path))
            return True

        if len(segment_files) == 1:
            shutil.copy2(str(segment_files[0]), str(output_path))
            return True

        # Concat all segments
        concat_list = Path(tmp) / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{str(f.resolve())}'" for f in segment_files),
            encoding='utf-8'
        )

        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_path)
        ]
        result = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"remove_dead_air concat failed: {result.stderr[-300:]}")
            shutil.copy2(str(input_path), str(output_path))
            return True

    logger.info(f"remove_dead_air: done → {output_path} "
                f"(original {total_dur:.1f}s, trimmed ~{sum(s['end']-s['start'] for s in keep_segments):.1f}s)")
    return True


def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter text parameter."""
    return (
        text.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace("%", "\\%")
    )


def generate_outro_card(
    output_path:  Path,
    duration_sec: float  = 2.5,
    style:        str    = "follow_handle",
    handle:       str    = "",
    custom_text:  str    = "",
    width:        int    = 1080,
    height:       int    = 1920,
) -> bool:
    """
    Generate a branded outro end card as MP4 using FFmpeg drawtext.

    Styles:
      follow_handle → "@{handle}" large + "for more" smaller below
      check_bio     → "Link in bio" large
      custom_text   → user's text, centered

    Returns True on success.
    """
    if style == "none":
        return False

    if style == "follow_handle":
        if not handle:
            handle = "us"
        line1 = handle if handle.startswith("@") else f"@{handle}"
        line2 = "for more"
    elif style == "check_bio":
        line1 = "Link in bio"
        line2 = ""
    else:  # custom_text
        line1 = custom_text or "Follow for more"
        line2 = ""

    # Font sizes relative to width
    font_size_main = max(24, int(width * 0.075))
    font_size_sub  = max(16, int(width * 0.042))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Font file detection with graceful fallback
    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    bold_param = f":fontfile={font_bold}" if os.path.exists(font_bold) else ""
    regular_param = f":fontfile={font_regular}" if os.path.exists(font_regular) else ""

    drawtext_filters = []

    esc_line1 = _escape_drawtext(line1)
    drawtext_filters.append(
        f"drawtext=text='{esc_line1}':"
        f"fontsize={font_size_main}:fontcolor=white{bold_param}:"
        f"x=(w-tw)/2:y=(h-th)/2-{font_size_main // 2}:"
        f"borderw=3:bordercolor=black"
    )

    if line2:
        esc_line2 = _escape_drawtext(line2)
        drawtext_filters.append(
            f"drawtext=text='{esc_line2}':"
            f"fontsize={font_size_sub}:fontcolor=white@0.7{regular_param}:"
            f"x=(w-tw)/2:y=(h-th)/2+{font_size_main}:"
            f"borderw=2:bordercolor=black"
        )

    vf = ",".join(drawtext_filters)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={width}x{height}:d={duration_sec}:r=30",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"generate_outro_card failed: {result.stderr[-300:]}")
            return False
        logger.info(f"Outro card generated: {output_path} ({duration_sec}s)")
        return True
    except Exception as e:
        logger.error(f"generate_outro_card exception: {e}")
        return False


def append_outro(
    main_clip:   Path,
    outro_card:  Path,
    output_path: Path
) -> bool:
    """
    Concatenate main clip + outro card using FFmpeg filter_complex concat.
    Resamples framerate, timestamps, and audio to avoid timebase stretching bugs.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    outro_dur = get_video_duration(outro_card) or 2.5

    try:
        if has_audio_stream(main_clip):
            cmd = [
                "ffmpeg", "-y",
                "-i", str(main_clip),
                "-i", str(outro_card),
                "-f", "lavfi", "-t", str(outro_dur), "-i", "anullsrc=r=44100:cl=stereo",
                "-filter_complex",
                "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a0];"
                "[2:a]aformat=sample_rates=44100:channel_layouts=stereo[a1];"
                "[0:v][a0][1:v][a1]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path)
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(main_clip),
                "-i", str(outro_card),
                "-filter_complex",
                "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-an",
                "-movflags", "+faststart",
                str(output_path)
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"append_outro concat failed: {result.stderr[-300:]}")
            return False

        logger.info(f"Outro appended: {output_path}")
        return True
    except Exception as e:
        logger.error(f"append_outro exception: {e}")
        return False


def auto_edit_full_video(
    source_path:  Path,
    clip_dir:     Path,
    restrictions: Dict[str, Any],
    campaign_name: str = "Clip"
) -> Optional[Dict[str, Any]]:
    """
    Main entry point for full_video_edit mode.
    
    Steps:
    1. Remove dead air (if enabled)
    2. Generate outro card (if style != none)
    3. Append outro
    
    Returns clip_data dict compatible with the existing pipeline,
    or None on failure.
    """
    clip_dir.mkdir(parents=True, exist_ok=True)

    remove_air   = restrictions.get('remove_dead_air', True)
    outro_style  = restrictions.get('outro_style', 'none')
    outro_text   = restrictions.get('outro_text', '')
    outro_handle = restrictions.get('outro_handle', '')
    threshold    = float(restrictions.get('silence_threshold_db', -40.0))
    gap_min      = float(restrictions.get('silence_gap_min_sec', 1.2))
    keep_sil     = float(restrictions.get('silence_keep_sec', 0.4))

    total_duration = get_video_duration(source_path)

    # Step 1: Remove dead air
    cleaned_path = clip_dir / "clip_cleaned.mp4"
    if remove_air:
        logger.info("Full edit: removing dead air...")
        ok = remove_dead_air(source_path, cleaned_path, threshold, gap_min, keep_sil)
        if not ok or not cleaned_path.exists():
            logger.warning("Dead air removal failed, using original source")
            shutil.copy2(str(source_path), str(cleaned_path))
    else:
        shutil.copy2(str(source_path), str(cleaned_path))

    edited_duration = get_video_duration(cleaned_path)

    # Step 2 + 3: Outro
    final_path = clip_dir / "clip_raw.mp4"

    if outro_style != 'none':
        outro_path = clip_dir / "outro.mp4"

        # Get dimensions of cleaned clip for matching outro size
        from .video_formatter import get_video_dimensions
        w, h = get_video_dimensions(cleaned_path)

        outro_ok = generate_outro_card(
            output_path=outro_path,
            duration_sec=2.5,
            style=outro_style,
            handle=outro_handle,
            custom_text=outro_text,
            width=w,
            height=h
        )

        if outro_ok and outro_path.exists():
            appended = append_outro(cleaned_path, outro_path, final_path)
            if not appended:
                logger.warning("Outro append failed, using clip without outro")
                shutil.copy2(str(cleaned_path), str(final_path))
        else:
            logger.warning("Outro card generation failed, using clip without outro")
            shutil.copy2(str(cleaned_path), str(final_path))
    else:
        shutil.copy2(str(cleaned_path), str(final_path))

    final_duration = get_video_duration(final_path)

    return {
        'moment_name':       campaign_name,
        'start_sec':         0.0,
        'end_sec':           final_duration,
        'duration_seconds':  final_duration,
        'video_file':        str(final_path),
        'full_edit':         True,
        'original_duration': total_duration,
        'edited_duration':   edited_duration,
        'outro_style':       outro_style
    }
