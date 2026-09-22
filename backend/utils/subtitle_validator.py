import logging
import os
import re
from pathlib import Path
from typing import Optional, Union

from .text_processor import TextProcessor

logger = logging.getLogger(__name__)

# Known dummy placeholder signatures
PLACEHOLDER_REGEX = re.compile(
    r'^\s*1\s*\n\s*00:00:00[,.]000\s*-->\s*00:00:05[,.]000\s*$',
    re.MULTILINE
)


def get_video_duration_seconds(video_path: Union[str, Path]) -> Optional[float]:
    """Inspects video file to get its duration in seconds via ffprobe or cv2."""
    vpath = Path(video_path)
    if not vpath.exists() or not vpath.is_file():
        return None
    
    try:
        from .video_processor import VideoProcessor
        vp = VideoProcessor()
        vinfo = vp.get_video_info(vpath)
        dur = vinfo.get("format", {}).get("duration")
        if dur is not None:
            return float(dur)
    except Exception as e:
        logger.debug(f"Failed to probe video duration via VideoProcessor: {e}")

    try:
        import subprocess
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(vpath)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception as e:
        logger.debug(f"Failed to probe video duration via ffprobe: {e}")

    return None


def validate_subtitle_file(
    srt_path: Optional[Union[str, Path]],
    video_path: Optional[Union[str, Path]] = None,
    min_cues: int = 1,
    min_duration_sec: float = 10.0,
    min_video_ratio: float = 0.10
) -> bool:
    """
    Validates whether an SRT subtitle file contains genuine, non-placeholder transcript content.

    Returns False if:
    - Path is None or file does not exist
    - File size is under 35 bytes
    - File matches known placeholder patterns (e.g. 5-second empty stub)
    - File contains no non-whitespace dialogue text
    - Video is longer than 30s but SRT duration is < min_duration_sec or < min_video_ratio of video length
    """
    if not srt_path:
        return False

    spath = Path(srt_path)
    if not spath.exists() or not spath.is_file():
        return False

    try:
        file_size = spath.stat().st_size
        if file_size < 35:
            logger.warning(f"Subtitle validation failed: file '{spath.name}' size ({file_size}b) is too small.")
            return False

        content = spath.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            logger.warning(f"Subtitle validation failed: file '{spath.name}' is empty.")
            return False

        # Check for placeholder markers
        if "PLACEHOLDER" in content.upper():
            logger.warning(f"Subtitle validation failed: file '{spath.name}' contains explicit placeholder marker.")
            return False

        if PLACEHOLDER_REGEX.match(content):
            logger.warning(f"Subtitle validation failed: file '{spath.name}' matches the 5-second dummy placeholder pattern.")
            return False

        tp = TextProcessor()
        cues = tp.parse_srt(spath)
        if not cues or len(cues) < min_cues:
            logger.warning(f"Subtitle validation failed: file '{spath.name}' contains only {len(cues) if cues else 0} cues (minimum {min_cues}).")
            return False

        # Ensure there is actual spoken dialogue text
        meaningful_cues = [c for c in cues if c.get("text", "").strip()]
        if not meaningful_cues:
            logger.warning(f"Subtitle validation failed: file '{spath.name}' has no text content in any cues.")
            return False

        # Calculate subtitle duration
        try:
            srt_start = tp.time_to_seconds(cues[0]["start_time"])
            srt_end = tp.time_to_seconds(cues[-1]["end_time"])
            srt_duration = max(0.0, srt_end - srt_start)
        except Exception as e:
            logger.warning(f"Subtitle validation failed: unable to parse timestamps in '{spath.name}': {e}")
            return False

        # If a single cue spans 5 seconds or less and has fewer than 4 words, reject as a stub
        total_words = sum(len(c.get("text", "").split()) for c in meaningful_cues)
        if len(meaningful_cues) <= 1 and srt_duration <= 5.0 and total_words < 4:
            logger.warning(f"Subtitle validation failed: '{spath.name}' is a trivial stub ({srt_duration:.1f}s, {total_words} words).")
            return False

        # Plausibility check against video duration if available
        if video_path:
            video_dur = get_video_duration_seconds(video_path)
            if video_dur and video_dur > 30.0:
                if srt_duration < min_duration_sec:
                    logger.warning(
                        f"Subtitle validation failed: '{spath.name}' duration ({srt_duration:.1f}s) "
                        f"is suspiciously short for a {video_dur:.1f}s video."
                    )
                    return False

                if srt_duration < (video_dur * min_video_ratio):
                    logger.warning(
                        f"Subtitle validation failed: '{spath.name}' duration ({srt_duration:.1f}s) "
                        f"covers less than {min_video_ratio*100:.0f}% of video duration ({video_dur:.1f}s)."
                    )
                    return False

        logger.debug(f"Subtitle validation passed: '{spath.name}' ({len(meaningful_cues)} cues, {srt_duration:.1f}s).")
        return True

    except Exception as e:
        logger.error(f"Error validating subtitle file '{spath}': {e}")
        return False
