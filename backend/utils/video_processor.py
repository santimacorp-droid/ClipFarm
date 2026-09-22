"""
Video Processing Utility
"""
import subprocess
import json
import logging
import re
import os
import sys
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
from .ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

# Fix import issues
try:
    from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR
except ImportError:
    # If relative import fails, attempt absolute import
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR

logger = logging.getLogger(__name__)


def detect_hw_accel() -> str:
    """
    Probe /dev/dri/renderD128 for VAAPI support on Linux.
    Returns: "vaapi" | "none"
    """
    use_hw = os.getenv("USE_HW_ACCEL", "auto").lower().strip()
    if use_hw == "none":
        return "none"
    if use_hw == "vaapi":
        return "vaapi"

    device = os.getenv("HW_ACCEL_DEVICE", "/dev/dri/renderD128")
    if Path(device).exists() and sys.platform.startswith("linux"):
        cmd = [
            get_ffmpeg_path(), "-nostdin", "-y",
            "-init_hw_device", f"vaapi=va:{device}",
            "-filter_hw_device", "va",
            "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
            "-vf", "format=nv12,hwupload",
            "-c:v", "h264_vaapi",
            "-f", "null", "-"
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return "vaapi"
        except Exception:
            pass
    return "none"


ACTIVE_HW_ACCEL = detect_hw_accel()
logger.info(f"[AutoClip] Active hardware acceleration: {ACTIVE_HW_ACCEL}")


def build_ffmpeg_cut_command(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    start_sec: Optional[float] = None,
    duration_sec: Optional[float] = None,
    use_hw_accel: bool = True,
    hw_device: str = "/dev/dri/renderD128",
    start_time: Optional[float] = None,
    end_time: Optional[float] = None
) -> List[str]:
    """
    Build FFmpeg command for cutting video.
    Supports (start_sec, duration_sec) or (start_time, end_time).
    When use_hw_accel=True and ACTIVE_HW_ACCEL == "vaapi":
        uses h264_vaapi with -qp 23
    Otherwise:
        uses libx264 with -preset veryfast -crf 22
    """
    if start_sec is None and start_time is not None:
        start_sec = start_time
    if duration_sec is None and end_time is not None and start_sec is not None:
        duration_sec = max(0.0, end_time - start_sec)

    start_sec = float(start_sec or 0.0)
    duration_sec = float(duration_sec or 0.0)

    ffmpeg_bin = get_ffmpeg_path()
    start_str = f"{start_sec:.3f}"
    dur_str = f"{duration_sec:.3f}"

    if use_hw_accel and (ACTIVE_HW_ACCEL == "vaapi" or os.getenv("USE_HW_ACCEL") == "vaapi") and Path(hw_device).exists():
        return [
            ffmpeg_bin, "-nostdin", "-y",
            "-init_hw_device", f"vaapi=va:{hw_device}",
            "-filter_hw_device", "va",
            "-ss", start_str,
            "-i", str(input_path),
            "-t", dur_str,
            "-vf", "format=nv12,hwupload",
            "-c:v", "h264_vaapi",
            "-qp", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path)
        ]
    else:
        return [
            ffmpeg_bin, "-nostdin", "-y",
            "-ss", start_str,
            "-i", str(input_path),
            "-t", dur_str,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path)
        ]

class VideoProcessor:
    """Video processing utility class"""
    
    def __init__(self, clips_dir: Optional[str] = None, collections_dir: Optional[str] = None, max_clip_duration: float = 600.0):
        # Require project-specific paths to avoid global path pollution
        if not clips_dir:
            raise ValueError("clips_dir argument is required; cannot use global path")
        if not collections_dir:
            raise ValueError("collections_dir argument is required; cannot use global path")
        
        self.clips_dir = Path(clips_dir)
        self.collections_dir = Path(collections_dir)
        self.max_clip_duration = max_clip_duration
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Clean filename to be 100% safe across filesystems and FFmpeg filter graphs.
        Strips quotes, commas, colons, brackets, and replaces spaces/punctuation with clean underscores.
        """
        if not filename:
            return "untitled"
        # Remove single/double quotes, commas, brackets, colons
        sanitized = re.sub(r'[\'\"`,:;<=>|?*\\/\[\]\(\)]', '', filename)
        # Replace spaces, tabs, dashes with clean underscores
        sanitized = re.sub(r'[\s\-]+', '_', sanitized)
        # Strip leading/trailing underscores and dots
        sanitized = sanitized.strip('._')
        # Limit length
        if len(sanitized) > 80:
            sanitized = sanitized[:80].rstrip('._')
        return sanitized or "clip"

    @staticmethod
    def get_hardware_encoder_config() -> Dict[str, Any]:
        """
        Detects AMD Ryzen 5 5600G iGPU VAAPI device (/dev/dri/renderD128)
        and configures hardware acceleration with quality preservation (-qp 23).
        """
        device = os.getenv("HW_ACCEL_DEVICE", "/dev/dri/renderD128")
        if (ACTIVE_HW_ACCEL == "vaapi" or os.getenv("USE_HW_ACCEL") == "vaapi") and Path(device).exists():
            return {
                "hw_init": ["-init_hw_device", f"vaapi=va:{device}", "-filter_hw_device", "va"],
                "upload_filter": ",format=nv12,hwupload",
                "codec_args": ["-c:v", "h264_vaapi", "-qp", "23"],
                "use_vaapi": True
            }
        return {
            "hw_init": [],
            "upload_filter": "",
            "codec_args": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"],
            "use_vaapi": False
        }
    
    @staticmethod
    def convert_srt_time_to_ffmpeg_time(srt_time: str) -> str:
        """
        Convert SRT timestamp format to FFmpeg timestamp format
        
        Args:
            srt_time: SRT time string (e.g. "00:00:06,140" or "00:00:06.140")
            
        Returns:
            FFmpeg time format (e.g. "00:00:06.140")
        """
        # Replace comma with dot
        return srt_time.replace(',', '.')
    
    @staticmethod
    def convert_seconds_to_ffmpeg_time(seconds: float) -> str:
        """
        Convert seconds to FFmpeg time format
        
        Args:
            seconds: Seconds as float
            
        Returns:
            FFmpeg time format (e.g. "00:00:06.140")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    
    @staticmethod
    def convert_ffmpeg_time_to_seconds(time_str: str) -> float:
        """
        Convert FFmpeg time string or seconds to float seconds
        
        Args:
            time_str: FFmpeg time string (e.g. "00:00:06.140", "00:00:06,140" or "6.14")
            
        Returns:
            Seconds as float
        """
        try:
            if time_str is None:
                return 0.0
            if isinstance(time_str, (int, float)):
                return float(time_str)
            s_val = str(time_str).strip().replace(',', '.')
            if ':' in s_val:
                parts = s_val.split(':')
                if len(parts) == 3:
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
            return float(s_val)
        except Exception as e:
            logger.error(f"Time format conversion failed: {time_str}, error: {e}")
            return 0.0

    @staticmethod
    def _escape_ffmpeg_filter_path(path: Path) -> str:
        """Escapes a file path for use inside FFmpeg filter strings (such as ass='...')."""
        p_str = str(path.resolve()).replace('\\', '/')
        p_str = p_str.replace(':', '\\:')
        p_str = p_str.replace("'", "'\\''")
        p_str = p_str.replace('[', '\\[').replace(']', '\\]')
        return p_str
    
    @staticmethod
    def extract_clip(input_video: Path, output_path: Path, 
                    start_time: str, end_time: str,
                    ass_path: Optional[Path] = None,
                    hook_banner_path: Optional[Path] = None,
                    watermark_path: Optional[Path] = None,
                    watermark_position: str = "bottom_right",
                    watermark_scale: float = 15.0,
                    watermark_opacity: float = 0.85,
                    watermark_margin: int = 24,
                    text_watermark_path: Optional[Path] = None,
                    watermark_text_position: str = "lower_center",
                    aspect_ratio: str = "9:16",
                    dynamic_zoom: bool = False,
                    bgm_track: Optional[str] = None,
                    bgm_volume: float = 0.18,
                    sfx_enabled: bool = False,
                    custom_bgm_path: Optional[str] = None,
                    max_clip_duration: float = 600.0) -> bool:
        """
        Extract clip from video with auto 9:16 vertical formatting (Reels/Shorts/TikTok), dynamic camera zoom,
        BGM auto-ducking, SFX hooks, ASS subtitle burn-in, color emoji hook banner, and logo/handle overlays
        """
        try:
            input_video = Path(input_video)
            output_path = Path(output_path)
            if ass_path:
                ass_path = Path(ass_path)
            if watermark_path:
                watermark_path = Path(watermark_path)
            if text_watermark_path:
                text_watermark_path = Path(text_watermark_path)
            if hook_banner_path:
                hook_banner_path = Path(hook_banner_path)

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            ffmpeg_bin = get_ffmpeg_path()
            
            # Convert timestamps from SRT format to FFmpeg format
            ffmpeg_start_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(start_time)
            ffmpeg_end_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(end_time)
            
            # Calculate duration and snap boundaries using silence detector
            start_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_start_time)
            end_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_end_time)
            
            try:
                from .silence_detector import AudioBoundarySnapper
                start_seconds, end_seconds = AudioBoundarySnapper.refine_clip_boundaries(
                    input_video, start_seconds, end_seconds, enable_snapping=True
                )
                ffmpeg_start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_seconds)
                ffmpeg_end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_seconds)
            except Exception as snap_err:
                logger.debug(f"Boundary snapping bypassed: {snap_err}")

            if end_seconds <= start_seconds:
                logger.warning(f"Invalid clip boundaries ({start_seconds}s -> {end_seconds}s), adjusting window to +30s")
                end_seconds = start_seconds + 30.0
                ffmpeg_end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_seconds)

            duration = min(max_clip_duration, max(5.0, end_seconds - start_seconds))
            
            # Probe input resolution
            in_w, in_h = 1920, 1080
            vinfo = VideoProcessor.get_video_info(input_video)
            if vinfo and 'streams' in vinfo:
                for stream in vinfo['streams']:
                    if stream.get('codec_type') == 'video':
                        in_w = int(stream.get('width', 1920))
                        in_h = int(stream.get('height', 1080))
                        break

            # Feature presence flags
            has_watermark = watermark_path is not None and watermark_path.exists()
            has_text_watermark = text_watermark_path is not None and text_watermark_path.exists()
            has_hook = hook_banner_path is not None and hook_banner_path.exists()
            has_subtitles = ass_path is not None and ass_path.exists()

            # Compute watermark positioning expressions
            from .watermark_processor import get_watermark_overlay_expr
            from .audio_enhancer import AudioEnhancer

            # Target canvas dimensions
            is_916 = str(aspect_ratio).lower() in [
                "9:16", "9:16_crop", "9:16_fill", "fill_9:16", "9:16_blur", "blur_9:16", "reel", "shorts",
                "9:16_split", "9:16_smart", "podcast_stacked", "auto", "9:16_smart_crop",
                "9:16_header", "header_black", "meme_canvas", "square_black"
            ]
            canvas_w = 1080 if is_916 else in_w
            canvas_h = 1920 if is_916 else in_h

            # Build unified software filter_complex graph
            filter_steps = []
            current_v = "0:v"

            # 1. Video formatting: 9:16 vertical format (1080x1920) or landscape
            from .smart_framing import SmartFramingEngine

            normalized_aspect = str(aspect_ratio).lower()
            if normalized_aspect in ["9:16_smart", "auto"]:
                analysis = SmartFramingEngine.analyze_video_framing(input_video)
                normalized_aspect = analysis.get("recommended_aspect_ratio", "9:16_blur")
                logger.info(f"Smart framing resolved layout '{normalized_aspect}' for {input_video.name}")

            if normalized_aspect in ["9:16_header", "header_black", "meme_canvas", "square_black"]:
                header_filter = SmartFramingEngine.build_black_header_canvas_filter(
                    in_w=in_w, in_h=in_h, canvas_w=canvas_w, canvas_h=canvas_h, header_h=520,
                    input_label=current_v, output_label="v_base"
                )
                filter_steps.append(header_filter)
                current_v = "v_base"
            elif normalized_aspect in ["9:16_split", "podcast_stacked"]:
                analysis = SmartFramingEngine.analyze_video_framing(input_video)
                sp = analysis.get("speaker_positions", [0.31, 0.69])
                s1 = sp[0] if len(sp) > 0 else 0.31
                s2 = sp[1] if len(sp) > 1 else 0.69
                split_filter = SmartFramingEngine.build_podcast_split_filter(
                    in_w=in_w, in_h=in_h, speaker1_cx=s1, speaker2_cx=s2,
                    canvas_w=canvas_w, canvas_h=canvas_h, input_label=current_v, output_label="v_base"
                )
                filter_steps.append(split_filter)
                current_v = "v_base"
            elif normalized_aspect in ["9:16_smart_crop"]:
                analysis = SmartFramingEngine.analyze_video_framing(input_video)
                sp = analysis.get("speaker_positions", [0.5])
                s_cx = sp[0] if sp else 0.5
                crop_filter = SmartFramingEngine.build_solo_smart_crop_filter(
                    in_w=in_w, in_h=in_h, speaker_cx=s_cx,
                    canvas_w=canvas_w, canvas_h=canvas_h, input_label=current_v, output_label="v_base"
                )
                filter_steps.append(crop_filter)
                current_v = "v_base"
            elif normalized_aspect in ["9:16_blur", "blur_9:16", "9:16"]:
                if in_w > in_h:
                    blur_filter = SmartFramingEngine.build_blurred_canvas_filter(
                        in_w=in_w, in_h=in_h, canvas_w=canvas_w, canvas_h=canvas_h,
                        input_label=current_v, output_label="v_base"
                    )
                    filter_steps.append(blur_filter)
                else:
                    filter_steps.append(
                        f"[{current_v}]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2[v_base]"
                    )
                current_v = "v_base"
            elif normalized_aspect in ["9:16_crop", "9:16_fill", "fill_9:16", "reel", "shorts"]:
                if in_w > in_h:
                    # Check if 2 speakers are detected: if so, never blind-center crop
                    analysis = SmartFramingEngine.analyze_video_framing(input_video)
                    if analysis.get("layout_type") == "podcast_2speaker":
                        logger.info("2 speakers detected in 9:16_crop mode; applying blurred canvas to prevent face clipping")
                        blur_filter = SmartFramingEngine.build_blurred_canvas_filter(
                            in_w=in_w, in_h=in_h, canvas_w=canvas_w, canvas_h=canvas_h,
                            input_label=current_v, output_label="v_base"
                        )
                        filter_steps.append(blur_filter)
                    else:
                        sp = analysis.get("speaker_positions", [0.5])
                        s_cx = sp[0] if sp else 0.5
                        crop_filter = SmartFramingEngine.build_solo_smart_crop_filter(
                            in_w=in_w, in_h=in_h, speaker_cx=s_cx,
                            canvas_w=canvas_w, canvas_h=canvas_h, input_label=current_v, output_label="v_base"
                        )
                        filter_steps.append(crop_filter)
                else:
                    filter_steps.append(
                        f"[{current_v}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v_base]"
                    )
                current_v = "v_base"

            # Track input indices for overlays
            next_input_idx = 1

            # 2. Watermark overlay (logo image)
            if has_watermark:
                scale_ratio = max(0.05, min(0.50, float(watermark_scale) / 100.0))
                wm_target_w = max(40, round(canvas_w * scale_ratio))
                op_val = max(0.05, min(1.0, float(watermark_opacity)))
                overlay_expr = get_watermark_overlay_expr(watermark_position, watermark_margin)
                filter_steps.append(
                    f"[{next_input_idx}:v]format=rgba,colorchannelmixer=aa={op_val},scale={wm_target_w}:-1[wm_scaled];"
                    f"[{current_v}][wm_scaled]overlay={overlay_expr}[v_wm]"
                )
                current_v = "v_wm"
                next_input_idx += 1

            # 2.5. Text Handle Watermark overlay (e.g. @yourhandle with opacity)
            if has_text_watermark:
                tw_expr = get_watermark_overlay_expr(watermark_text_position, watermark_margin)
                filter_steps.append(
                    f"[{next_input_idx}:v]format=rgba[tw_scaled];"
                    f"[{current_v}][tw_scaled]overlay={tw_expr}[v_tw]"
                )
                current_v = "v_tw"
                next_input_idx += 1

            # 3. ASS subtitle burn-in
            if has_subtitles:
                escaped_ass = VideoProcessor._escape_ffmpeg_filter_path(ass_path)
                filter_steps.append(
                    f"[{current_v}]ass='{escaped_ass}'[v_sub]"
                )
                current_v = "v_sub"

            # 3.5. Top Hook Banner overlay
            if has_hook:
                hook_input_idx = next_input_idx
                next_input_idx += 1
                if normalized_aspect in ["9:16_header", "header_black", "meme_canvas", "square_black"]:
                    # Persistent meme/story top header for the entire clip duration
                    filter_steps.append(
                        f"[{hook_input_idx}:v]format=rgba[hook_hdr];"
                        f"[{current_v}][hook_hdr]overlay=0:0:shortest=1[v_hook]"
                    )
                else:
                    hook_y = int(canvas_h * 0.09) if is_916 else int(canvas_h * 0.06)
                    fade_duration = min(4.2, duration - 0.2)
                    filter_steps.append(
                        f"[{hook_input_idx}:v]format=rgba,"
                        f"fade=t=in:st=0:d=0.35:alpha=1,"
                        f"fade=t=out:st={max(0.1, fade_duration - 0.40):.2f}:d=0.40:alpha=1[hook_faded];"
                        f"[{current_v}][hook_faded]overlay=x=(W-w)/2:y={hook_y}:enable='between(t,0,{fade_duration:.2f})'[v_hook]"
                    )
                current_v = "v_hook"

            # 4. Audio enhancement (BGM sidechain ducking + SFX)
            extra_input_offset = next_input_idx
            extra_audio_inputs, audio_filter_fragment, audio_out_node = AudioEnhancer.build_audio_filter_graph(
                bgm_track=bgm_track,
                bgm_volume=bgm_volume,
                sfx_enabled=sfx_enabled,
                base_input_offset=extra_input_offset,
                custom_bgm_path=custom_bgm_path
            )

            # Build audio fade if no custom audio filter fragment
            audio_fade_filter = ""
            if not audio_filter_fragment:
                fade_out_st = max(0.1, duration - 0.20)
                audio_fade_filter = f"[0:a]afade=t=in:ss=0:d=0.15,afade=t=out:st={fade_out_st:.2f}:d=0.20[outa]"
                audio_out_node = "[outa]"

            # Fast stream copy when no video or audio filters are required
            if not filter_steps and not audio_filter_fragment:
                cmd_copy = [
                    ffmpeg_bin, '-nostdin', '-y',
                    '-ss', ffmpeg_start_time,
                    '-i', str(input_video),
                    '-t', str(duration),
                    '-c:v', 'copy',
                    '-c:a', 'copy',
                    '-avoid_negative_ts', 'make_zero',
                    str(output_path)
                ]
                res_copy = subprocess.run(cmd_copy, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if res_copy.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                    logger.info(f"Fast stream copy export succeeded: {output_path.name} (near-zero CPU, duration: {duration:.2f}s)")
                    return True

            # Execute with Hardware Acceleration (AMD Ryzen iGPU VAAPI)
            hw_cfg = VideoProcessor.get_hardware_encoder_config()
            encoded_successfully = False

            if filter_steps or audio_filter_fragment:
                # Primary Attempt: VAAPI iGPU Hardware Encoding
                vaapi_steps = list(filter_steps)
                if hw_cfg["use_vaapi"]:
                    # CRITICAL FIX: Upload software frame to GPU VAAPI memory surface
                    vaapi_steps.append(f"[{current_v}]format=nv12,hwupload[outv]")
                else:
                    vaapi_steps.append(f"[{current_v}]null[outv]")

                if audio_filter_fragment:
                    vaapi_steps.append(audio_filter_fragment)
                elif audio_fade_filter:
                    vaapi_steps.append(audio_fade_filter)

                vaapi_filter_graph = ";".join(vaapi_steps)
                cmd_vaapi = [ffmpeg_bin, '-nostdin', '-y']
                if hw_cfg["hw_init"]:
                    cmd_vaapi.extend(hw_cfg["hw_init"])
                cmd_vaapi.extend([
                    '-ss', ffmpeg_start_time,
                    '-i', str(input_video)
                ])
                if has_watermark:
                    cmd_vaapi.extend(['-i', str(watermark_path)])
                if has_text_watermark:
                    cmd_vaapi.extend(['-i', str(text_watermark_path)])
                if has_hook:
                    cmd_vaapi.extend(['-loop', '1', '-i', str(hook_banner_path)])
                if extra_audio_inputs:
                    cmd_vaapi.extend(extra_audio_inputs)

                cmd_vaapi.extend([
                    '-t', str(duration),
                    '-filter_complex', vaapi_filter_graph,
                    '-map', '[outv]',
                    '-map', audio_out_node if audio_out_node else '0:a?'
                ])
                cmd_vaapi.extend(hw_cfg["codec_args"])
                cmd_vaapi.extend([
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-avoid_negative_ts', 'make_zero',
                    str(output_path)
                ])

                logger.info(f"Executing FFmpeg short-form processing (VAAPI={hw_cfg['use_vaapi']}, 9:16={is_916}, Zoom={dynamic_zoom}, BGM={bgm_track}, SFX={sfx_enabled}): {output_path.name}")
                res = subprocess.run(cmd_vaapi, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                    logger.info(f"Successfully exported 9:16 clip video (iGPU/VAAPI): {output_path.name} (duration: {duration:.2f}s)")
                    return True
                else:
                    logger.warning(f"VAAPI filter processing failed: {res.stderr[:300] if res.stderr else 'Unknown error'}, attempting robust CPU re-encode fallback WITH filters...")

                # Secondary Fallback: CPU Re-encode WITH ALL FILTERS (Never strip subtitles/watermark!)
                cpu_steps = list(filter_steps)
                cpu_steps.append(f"[{current_v}]null[outv]")
                if audio_filter_fragment:
                    cpu_steps.append(audio_filter_fragment)
                elif audio_fade_filter:
                    cpu_steps.append(audio_fade_filter)

                cmd_cpu = [
                    ffmpeg_bin,
                    '-nostdin', '-y',
                    '-ss', ffmpeg_start_time,
                    '-i', str(input_video)
                ]
                if has_watermark:
                    cmd_cpu.extend(['-i', str(watermark_path)])
                if has_text_watermark:
                    cmd_cpu.extend(['-i', str(text_watermark_path)])
                if has_hook:
                    cmd_cpu.extend(['-loop', '1', '-i', str(hook_banner_path)])
                if extra_audio_inputs:
                    cmd_cpu.extend(extra_audio_inputs)

                cmd_cpu.extend([
                    '-t', str(duration),
                    '-filter_complex', ";".join(cpu_steps),
                    '-map', '[outv]',
                    '-map', audio_out_node if audio_out_node else '0:a?',
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-crf', '22',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-avoid_negative_ts', 'make_zero',
                    str(output_path)
                ])
                res_cpu = subprocess.run(cmd_cpu, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if res_cpu.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                    logger.info(f"Successfully exported 9:16 clip video (CPU Fallback): {output_path.name} (duration: {duration:.2f}s)")
                    return True
                else:
                    logger.warning(f"CPU filter processing failed: {res_cpu.stderr[:300] if res_cpu.stderr else 'Unknown error'}")

            # Last resort fallback: direct stream copy if all filtered methods fail
            cmd_copy = [
                ffmpeg_bin,
                '-nostdin', '-y',
                '-ss', ffmpeg_start_time,
                '-i', str(input_video),
                '-t', str(duration),
                '-c:v', 'copy',
                '-c:a', 'copy',
                '-avoid_negative_ts', 'make_zero',
                str(output_path)
            ]
            result_copy = subprocess.run(cmd_copy, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result_copy.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                logger.warning(f"Used raw copy mode for: {output_path.name} (filters omitted)")
                return True

            logger.error(f"Failed to extract video clip: {output_path.name}")
            return False
                
        except Exception as e:
            logger.error(f"Video processing exception: {str(e)}")
            return False
    
    @staticmethod
    def create_collection(clips_list: List[Path], output_path: Path) -> bool:
        """
        Concatenate multiple video clips into a collection
        
        Args:
            clips_list: List of video clip paths
            output_path: Output collection path
            
        Returns:
            Whether operation succeeded
        """
        try:
            # Validate input arguments
            if not clips_list:
                logger.error("clips_list is empty, cannot create collection")
                return False
            
            # Validate all video files exist
            valid_clips = []
            for clip_path in clips_list:
                if not clip_path.exists():
                    logger.warning(f"Video file does not exist, skipping: {clip_path}")
                    continue
                valid_clips.append(clip_path)
            
            if not valid_clips:
                logger.error("No valid video files found, cannot create collection")
                return False
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create concat demuxer file
            concat_file = output_path.parent / "concat_list.txt"
            
            with open(concat_file, 'w', encoding='utf-8') as f:
                for clip_path in valid_clips:
                    # Use absolute paths and escape single quotes
                    abs_path = clip_path.absolute()
                    escaped_path = str(abs_path).replace("'", "'\"'\"'")
                    f.write(f"file '{escaped_path}'\n")
            
            # Validate concat file content
            if concat_file.stat().st_size == 0:
                logger.error("Concat file is empty, cannot create collection")
                concat_file.unlink(missing_ok=True)
                return False
            
            # Build FFmpeg command - prioritize hardware encoder
            ffmpeg_bin = get_ffmpeg_path()
            hw_cfg = VideoProcessor.get_hardware_encoder_config()
            if hw_cfg["use_vaapi"]:
                cmd = [
                    ffmpeg_bin,
                    *hw_cfg["hw_init"],
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_file),
                    '-vf', 'format=nv12,hwupload',
                    *hw_cfg["codec_args"],
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-y',
                    str(output_path)
                ]
            else:
                cmd = [
                    ffmpeg_bin,
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_file),
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-crf', '22',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-y',
                    str(output_path)
                ]
            
            logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            # Clean up temporary files
            concat_file.unlink(missing_ok=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully created collection: {output_path}")
                return True
            else:
                logger.error(f"Failed to create collection: {result.stderr}")
                logger.error(f"FFmpeg stdout: {result.stdout}")
                return False
                
        except Exception as e:
            logger.error(f"Video concatenation exception: {str(e)}")
            return False
    
    @staticmethod
    def extract_thumbnail(video_path: Path, output_path: Path, time_offset: int = 5) -> bool:
        """
        Extract thumbnail frame from video
        
        Args:
            video_path: Path to video file
            output_path: Output thumbnail path
            time_offset: Time offset in seconds
            
        Returns:
            Whether operation succeeded
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(time_offset),
                '-vframes', '1',
                '-q:v', '2',  # High quality
                '-y',  # Overwrite output file
                str(output_path)
            ]
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0 and output_path.exists():
                logger.info(f"Successfully extracted thumbnail: {output_path}")
                return True
            else:
                logger.error(f"Failed to extract thumbnail: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Exception extracting thumbnail: {str(e)}")
            return False
    
    @staticmethod
    def get_video_info(video_path: Path) -> Dict:
        """
        Get video metadata
        
        Args:
            video_path: Path to video file
            
        Returns:
            Video metadata dict
        """
        try:
            video_path = Path(video_path)
            ffprobe_bin = get_ffprobe_path()
            cmd = [
                ffprobe_bin,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                return {
                    'duration': float(info['format']['duration']),
                    'size': int(info['format']['size']),
                    'bitrate': int(info['format']['bit_rate']),
                    'streams': info['streams']
                }
            else:
                logger.error(f"Failed to get video metadata: {result.stderr}")
                return {}
                
        except Exception as e:
            logger.error(f"Exception getting video metadata: {str(e)}")
            return {}
    
    def batch_extract_clips(
        self, 
        input_video: Path, 
        clips_data: List[Dict],
        srt_path: Optional[Path] = None,
        caption_style: str = "hormozi_yellow",
        show_hook_banner: bool = True,
        watermark_path: Optional[Path] = None,
        watermark_position: str = "bottom_right",
        watermark_scale: float = 15.0,
        watermark_opacity: float = 0.85,
        watermark_margin: int = 24,
        watermark_text: Optional[str] = None,
        watermark_text_opacity: float = 0.50,
        watermark_text_position: str = "lower_center",
        aspect_ratio: str = "9:16",
        dynamic_zoom: bool = False,
        bgm_track: Optional[str] = None,
        bgm_volume: float = 0.18,
        sfx_enabled: bool = False,
        custom_bgm_path: Optional[str] = None,
        category: str = "general",
        tracker: Optional[Any] = None
    ) -> List[Path]:
        """
        Extract video clips with dynamic viral captions, optional top hook headlines, watermark overlays,
        dynamic punch-in zooming, and background music (BGM) + SFX.
        
        Args:
            input_video: Input video path
            clips_data: List of clip dicts with id, title, start_time, end_time
            srt_path: Optional source SRT subtitle file
            caption_style: Subtitle style ('hormozi_yellow', 'neon_green', 'neon_cyan', 'clean_box', 'none')
            show_hook_banner: Whether to burn the top hook headline banner
            watermark_path: Optional PNG/logo image path
            watermark_position: Corner position ('bottom_right', 'bottom_left', 'top_right', 'top_left')
            watermark_scale: Width relative to video width (percentage)
            watermark_opacity: Watermark opacity (0.05 to 1.0)
            watermark_margin: Margin in pixels from frame edge
            watermark_text: Optional social handle or text watermark (e.g. '@yourhandle')
            watermark_text_opacity: Opacity for text watermark (0.1 to 1.0)
            watermark_text_position: Position for text watermark ('lower_center', 'bottom_right', etc.)
            aspect_ratio: Video aspect ratio ('9:16', '9:16_header', '16:9', 'original')
            dynamic_zoom: Enable punch-in zoom cuts
            bgm_track: BGM track preset ('suspense', 'lofi', 'upbeat', 'none')
            bgm_volume: BGM volume
            sfx_enabled: Enable SFX on hook & transitions
            
        Returns:
            List of successfully generated clip paths
        """
        input_video = Path(input_video)
        if srt_path:
            srt_path = Path(srt_path)
        if watermark_path:
            watermark_path = Path(watermark_path)
        successful_clips = []
        
        # Determine target output resolution
        if str(aspect_ratio).lower() in [
            "9:16", "9:16_blur", "9:16_crop", "9:16_fill", "fill_9:16", "blur_9:16", "reel", "shorts",
            "9:16_split", "9:16_smart", "podcast_stacked", "auto", "9:16_smart_crop",
            "9:16_header", "header_black", "meme_canvas", "square_black"
        ]:
            target_width = 1080
            target_height = 1920
        else:
            target_width = 1920
            target_height = 1080
            video_info = self.get_video_info(input_video)
            if video_info and 'streams' in video_info:
                for stream in video_info['streams']:
                    if stream.get('codec_type') == 'video':
                        target_width = int(stream.get('width', 1920))
                        target_height = int(stream.get('height', 1080))
                        break

        hooks_map = {}
        if show_hook_banner and clips_data:
            try:
                from .hook_generator import ViralHookGenerator
                hooks_map = ViralHookGenerator.batch_generate_hooks(
                    clips_data,
                    video_title=input_video.stem,
                    category=category
                )
                logger.info(f"Pre-generated {len(hooks_map)} viral hooks in a single batch request (category={category}).")
            except Exception as h_err:
                logger.debug(f"Batch hook pre-generation bypassed: {h_err}")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        from ..core.shared_config import FFMPEG_MAX_PARALLEL_CUTS

        workers = max(1, min(len(clips_data), FFMPEG_MAX_PARALLEL_CUTS))
        logger.info(f"[AutoClip] Cutting {len(clips_data)} clips with ThreadPoolExecutor (max_workers={workers}, cap={FFMPEG_MAX_PARALLEL_CUTS})...")

        clip_results = [None] * len(clips_data)
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_idx = {
                    executor.submit(
                        self._cut_single_clip,
                        input_video=input_video,
                        clip_data=clip,
                        hooks_map=hooks_map,
                        target_width=target_width,
                        target_height=target_height,
                        srt_path=srt_path,
                        caption_style=caption_style,
                        show_hook_banner=show_hook_banner,
                        watermark_path=watermark_path,
                        watermark_position=watermark_position,
                        watermark_scale=watermark_scale,
                        watermark_opacity=watermark_opacity,
                        watermark_margin=watermark_margin,
                        watermark_text=watermark_text,
                        watermark_text_opacity=watermark_text_opacity,
                        watermark_text_position=watermark_text_position,
                        aspect_ratio=aspect_ratio,
                        dynamic_zoom=dynamic_zoom,
                        bgm_track=bgm_track,
                        bgm_volume=bgm_volume,
                        sfx_enabled=sfx_enabled,
                        custom_bgm_path=custom_bgm_path,
                        tracker=tracker,
                        clip_idx=idx,
                        total_clips=len(clips_data)
                    ): idx
                    for idx, clip in enumerate(clips_data)
                }
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        res = future.result()
                        if res and res.exists():
                            clip_results[idx] = res
                    except Exception as f_err:
                        logger.warning(f"[AutoClip] Clip {idx + 1} thread raised exception: {f_err}")

            successful_clips = [p for p in clip_results if p is not None]

            # Sequential retry for any clips that failed during parallel execution
            if len(successful_clips) < len(clips_data):
                logger.warning(
                    f"[AutoClip] Only {len(successful_clips)}/{len(clips_data)} clips generated in parallel; retrying missing clips sequentially..."
                )
                for idx, clip in enumerate(clips_data):
                    if clip_results[idx] is None:
                        res = self._cut_single_clip(
                            input_video=input_video,
                            clip_data=clip,
                            hooks_map=hooks_map,
                            target_width=target_width,
                            target_height=target_height,
                            srt_path=srt_path,
                            caption_style=caption_style,
                            show_hook_banner=show_hook_banner,
                            watermark_path=watermark_path,
                            watermark_position=watermark_position,
                            watermark_scale=watermark_scale,
                            watermark_opacity=watermark_opacity,
                            watermark_margin=watermark_margin,
                            watermark_text=watermark_text,
                            watermark_text_opacity=watermark_text_opacity,
                            watermark_text_position=watermark_text_position,
                            aspect_ratio=aspect_ratio,
                            dynamic_zoom=dynamic_zoom,
                            bgm_track=bgm_track,
                            bgm_volume=bgm_volume,
                            sfx_enabled=sfx_enabled,
                            custom_bgm_path=custom_bgm_path,
                            tracker=tracker,
                            clip_idx=idx,
                            total_clips=len(clips_data)
                        )
                        if res and res.exists():
                            clip_results[idx] = res
                successful_clips = [p for p in clip_results if p is not None]
        except Exception as pool_err:
            logger.warning(f"[AutoClip] Parallel cutting encountered an error ({pool_err}), falling back to sequential execution...")
            successful_clips = []
            for idx, clip in enumerate(clips_data):
                res = self._cut_single_clip(
                    input_video=input_video,
                    clip_data=clip,
                    hooks_map=hooks_map,
                    target_width=target_width,
                    target_height=target_height,
                    srt_path=srt_path,
                    caption_style=caption_style,
                    show_hook_banner=show_hook_banner,
                    watermark_path=watermark_path,
                    watermark_position=watermark_position,
                    watermark_scale=watermark_scale,
                    watermark_opacity=watermark_opacity,
                    watermark_margin=watermark_margin,
                    aspect_ratio=aspect_ratio,
                    dynamic_zoom=dynamic_zoom,
                    bgm_track=bgm_track,
                    bgm_volume=bgm_volume,
                    sfx_enabled=sfx_enabled,
                    custom_bgm_path=custom_bgm_path,
                    tracker=tracker,
                    clip_idx=idx,
                    total_clips=len(clips_data)
                )
                if res and res.exists():
                    successful_clips.append(res)

        return successful_clips

    def _cut_single_clip(
        self,
        input_video: Path,
        clip_data: Dict,
        hooks_map: Dict,
        target_width: int,
        target_height: int,
        srt_path: Optional[Path] = None,
        caption_style: str = "hormozi_yellow",
        show_hook_banner: bool = True,
        watermark_path: Optional[Path] = None,
        watermark_position: str = "bottom_right",
        watermark_scale: float = 15.0,
        watermark_opacity: float = 0.85,
        watermark_margin: int = 24,
        watermark_text: Optional[str] = None,
        watermark_text_opacity: float = 0.50,
        watermark_text_position: str = "lower_center",
        aspect_ratio: str = "9:16",
        dynamic_zoom: bool = False,
        bgm_track: Optional[str] = None,
        bgm_volume: float = 0.18,
        sfx_enabled: bool = False,
        custom_bgm_path: Optional[str] = None,
        tracker: Optional[Any] = None,
        clip_idx: int = 0,
        total_clips: int = 1
    ) -> Optional[Path]:
        """Extract a single video clip with subtitles, watermarks, framing and audio enhancements."""
        try:
            input_video = Path(input_video)
            if srt_path:
                srt_path = Path(srt_path)
            if watermark_path:
                watermark_path = Path(watermark_path)

            clip_id = clip_data['id']
            title = clip_data.get('title') or clip_data.get('generated_title') or clip_data.get('outline') or f"clip_{clip_id}"
            if tracker:
                tracker.set_substep(
                    f"Cutting clip {clip_idx + 1} of {total_clips}: {title[:40]}",
                    current=clip_idx + 1,
                    total=total_clips
                )
            start_time = clip_data['start_time']
            end_time = clip_data['end_time']
            
            # Normalize timestamp format to SRT format if provided as seconds
            if isinstance(start_time, (int, float)):
                start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
            if isinstance(end_time, (int, float)):
                end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)
            
            # Convert to seconds for subtitle slicing
            start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(start_time)
            end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(end_time)

            # Sanitize title for filesystem filename
            safe_title = VideoProcessor.sanitize_filename(title)
            output_path = self.clips_dir / f"{clip_id}_{safe_title}.mp4"
            clip_srt_path = self.clips_dir / f"{clip_id}_{safe_title}.srt"
            clip_ass_path = self.clips_dir / f"{clip_id}_{safe_title}.ass"
            
            # Generate dedicated .srt and .ass subtitles if source subtitles exist
            ass_to_burn: Optional[Path] = None
            hook_banner_png: Optional[Path] = None
            text_wm_png: Optional[Path] = None

            # Render custom text handle watermark if specified (e.g. @yourhandle)
            effective_wm_text = clip_data.get('watermark_text') or watermark_text
            effective_wm_opacity = clip_data.get('watermark_text_opacity') if clip_data.get('watermark_text_opacity') is not None else watermark_text_opacity
            effective_wm_pos = clip_data.get('watermark_text_position') or watermark_text_position
            if effective_wm_text and str(effective_wm_text).strip() and str(effective_wm_text).lower() != 'none':
                try:
                    from .watermark_processor import render_text_watermark
                    text_wm_png = output_path.parent / f"{output_path.stem}_handle_wm.png"
                    render_text_watermark(
                        text=str(effective_wm_text).strip(),
                        output_path=text_wm_png,
                        opacity=effective_wm_opacity
                    )
                    if not text_wm_png.exists() or text_wm_png.stat().st_size == 0:
                        text_wm_png = None
                    else:
                        logger.info(f"Generated text watermark PNG for clip {clip_id}: '{effective_wm_text}' -> {text_wm_png}")
                except Exception as tw_err:
                    logger.debug(f"Failed to render text handle watermark: {tw_err}")
                    text_wm_png = None

            if srt_path and srt_path.exists():
                try:
                    from .caption_styles import ViralCaptionGenerator

                    # Look for companion word timestamps JSON
                    words_data = None
                    words_cands = [
                        srt_path.parent / f"{srt_path.stem}_words.json",
                        srt_path.parent / "step2_words.json",
                        srt_path.parent / "words.json",
                        srt_path.parent.parent / "metadata" / "step2_words.json",
                        srt_path.parent.parent / "metadata" / "words.json",
                    ]
                    for w_cand in words_cands:
                        if w_cand.exists():
                            try:
                                import json
                                with open(w_cand, 'r', encoding='utf-8') as f:
                                    loaded_words = json.load(f)
                                if isinstance(loaded_words, list) and loaded_words:
                                    words_data = loaded_words
                                    break
                            except Exception:
                                pass

                    # Generate dedicated clip SRT for export/download
                    ViralCaptionGenerator.generate_clip_srt(
                        source_srt_path=srt_path,
                        clip_start=start_sec,
                        clip_end=end_sec,
                        output_srt_path=clip_srt_path,
                        words_data=words_data
                    )

                    # If subtitle burn-in is enabled (style is not none)
                    active_style = caption_style if (caption_style and caption_style.lower() != "none") else "hormozi_yellow"
                    if ViralCaptionGenerator.generate_clip_ass(
                        source_srt_path=srt_path,
                        clip_start=start_sec,
                        clip_end=end_sec,
                        output_ass_path=clip_ass_path,
                        style_key=active_style,
                        hook_title=None,
                        show_hook_banner=False,
                        video_width=target_width,
                        video_height=target_height,
                        words_data=words_data,
                        word_segments=words_data
                    ):
                        ass_to_burn = clip_ass_path
                except Exception as cap_err:
                    logger.warning(f"Failed to generate subtitle files for clip {clip_id}: {cap_err}")

            # Determine top viral hook headline banner
            hook_banner_text = clip_data.get('hook_text') or clip_data.get('hook_title')
            if (not hook_banner_text or hook_banner_text in [title, f"clip_{clip_id}", "Short Clip", "input.mp4"]) and clip_id in hooks_map:
                h_val = hooks_map[clip_id]
                hook_banner_text = h_val.get("hook_headline") if isinstance(h_val, dict) else str(h_val)
            elif not hook_banner_text or hook_banner_text in [title, f"clip_{clip_id}", "Short Clip", "input.mp4"]:
                try:
                    from .hook_generator import ViralHookGenerator
                    clip_transcript = clip_srt_path.read_text(encoding="utf-8", errors="ignore") if clip_srt_path.exists() else ""
                    if clip_transcript:
                        hook_info = ViralHookGenerator.generate_hook_from_transcript(
                            clip_transcript,
                            video_title=title,
                            category=clip_data.get('category', 'general'),
                            recommend_reason=clip_data.get('recommend_reason')
                        )
                        hook_banner_text = hook_info.get("hook_headline")
                except Exception:
                    hook_banner_text = None
            
            if not hook_banner_text:
                hook_banner_text = clip_data.get('hook_text') or clip_data.get('generated_title') or title

            # Ensure hook banner has clean formatting
            if hook_banner_text:
                try:
                    from .hook_generator import ensure_hook_has_color_emojis
                    hook_banner_text = ensure_hook_has_color_emojis(
                        hook_banner_text, 
                        category=clip_data.get('category', 'general')
                    )
                except Exception as e_em:
                    logger.debug(f"Emoji hook enhancement skipped: {e_em}")

            # Render top hook banner (Black Header for 9:16_header mode, frosted glass banner for standard mode)
            is_header_canvas = str(aspect_ratio).lower() in ["9:16_header", "header_black", "meme_canvas", "square_black"]
            if show_hook_banner and hook_banner_text:
                try:
                    hook_banner_png = output_path.parent / f"{output_path.stem}_hook_banner.png"
                    if is_header_canvas:
                        from .hook_overlay import render_black_header_hook
                        render_black_header_hook(
                            text=hook_banner_text,
                            canvas_w=target_width,
                            header_h=520,
                            output_path=hook_banner_png
                        )
                    else:
                        from .hook_overlay import render_color_emoji_hook_banner
                        render_color_emoji_hook_banner(
                            text=hook_banner_text,
                            video_width=target_width,
                            video_height=target_height,
                            output_path=hook_banner_png,
                            category=clip_data.get('category', 'general')
                        )
                    if not hook_banner_png.exists() or hook_banner_png.stat().st_size == 0:
                        hook_banner_png = None
                    else:
                        logger.info(f"Generated hook banner PNG for clip {clip_id}: \"{hook_banner_text}\" -> {hook_banner_png}")
                except Exception as h_png_err:
                    logger.warning(f"Failed to render hook banner PNG for clip {clip_id}: {h_png_err}")
                    hook_banner_png = None

            logger.info(f"Extracting clip {clip_id}: {start_time} -> {end_time}, output: {output_path.name}, style: {caption_style}, ratio: {aspect_ratio}, Zoom: {dynamic_zoom}, BGM: {bgm_track}, SFX: {sfx_enabled}, Hook: {bool(hook_banner_png)}, TextWM: {bool(text_wm_png)}")
            
            if VideoProcessor.extract_clip(
                input_video, 
                output_path, 
                start_time, 
                end_time, 
                ass_path=ass_to_burn,
                hook_banner_path=hook_banner_png,
                watermark_path=watermark_path,
                watermark_position=watermark_position,
                watermark_scale=watermark_scale,
                watermark_opacity=watermark_opacity,
                watermark_margin=watermark_margin,
                text_watermark_path=text_wm_png,
                watermark_text_position=effective_wm_pos,
                aspect_ratio=aspect_ratio,
                dynamic_zoom=dynamic_zoom,
                bgm_track=bgm_track,
                bgm_volume=bgm_volume,
                sfx_enabled=sfx_enabled,
                custom_bgm_path=custom_bgm_path,
                max_clip_duration=self.max_clip_duration
            ):
                logger.info(f"Clip {clip_id} extracted successfully")
                if tracker:
                    tracker.log(f"Clip {clip_idx + 1} done: {output_path.name}")
                return output_path
            else:
                logger.error(f"Clip {clip_id} extraction failed")
                return None
        except Exception as err:
            logger.error(f"Error cutting clip {clip_data.get('id', 'unknown')}: {err}")
            return None
    
    def create_collections_from_metadata(self, collections_data: List[Dict]) -> List[Dict]:
        """
        Create collections according to metadata
        
        Args:
            collections_data: List of collection metadata
            
        Returns:
            List of created collection info dicts with video and thumbnail paths
        """
        successful_collections = []
        
        for collection_data in collections_data:
            collection_id = collection_data['id']
            collection_title = collection_data.get('collection_title', f'Collection_{collection_id}')
            clip_ids = collection_data['clip_ids']
            
            # Build clip paths list
            clips_list = []
            for clip_id in clip_ids:
                # Locate corresponding clip file
                # Filename format: {clip_id}_{title}.mp4
                clip_path = self.clips_dir / f"{clip_id}_*.mp4"
                found_clips = list(self.clips_dir.glob(f"{clip_id}_*.mp4"))
                
                if found_clips:
                    found_clip = found_clips[0]  # Take first matching file
                    clips_list.append(found_clip)
                    logger.info(f"Found clip for collection {collection_id}: {found_clip.name}")
                else:
                    logger.warning(f"Clip {clip_id} not found for collection {collection_id}")
            
            if clips_list:
                # Sanitize collection title for filename
                safe_title = VideoProcessor.sanitize_filename(collection_title)
                output_path = self.collections_dir / f"{safe_title}.mp4"
                
                if VideoProcessor.create_collection(clips_list, output_path):
                    # Generate collection thumbnail
                    thumbnail_path = None
                    try:
                        thumbnail_filename = f"{collection_id}_{safe_title}_thumbnail.jpg"
                        thumbnail_path = self.collections_dir / thumbnail_filename
                        
                        # Extract thumbnail frame from video at 2.0s mark
                        thumbnail_success = VideoProcessor.extract_thumbnail(output_path, thumbnail_path, time_offset=2)
                        if thumbnail_success:
                            logger.info(f"Collection {collection_id} thumbnail generated successfully: {thumbnail_path}")
                        else:
                            logger.warning(f"Failed to generate thumbnail for collection {collection_id}")
                            thumbnail_path = None
                    except Exception as e:
                        logger.error(f"Error generating thumbnail for collection {collection_id}: {e}")
                        thumbnail_path = None
                    
                    # Return info with video and thumbnail paths
                    collection_info = {
                        'collection_id': collection_id,
                        'video_path': str(output_path),
                        'thumbnail_path': str(thumbnail_path) if thumbnail_path else None,
                        'title': collection_title
                    }
                    successful_collections.append(collection_info)
                    logger.info(f"Successfully created collection {collection_id}: {output_path}")
            else:
                logger.warning(f"Collection {collection_id} found no valid clip files")
        
        return successful_collections