"""
Convert campaign clip videos to 9:16 vertical format for TikTok, Reels, and Shorts.
"""
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

TARGET_WIDTH  = 1080
TARGET_HEIGHT = 1920

def get_video_dimensions(video_path: Path) -> Tuple[int, int]:
    """Return (width, height) of a video file using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                str(video_path)
            ],
            capture_output=True, text=True, timeout=30
        )
        parts = result.stdout.strip().split(",")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except Exception as e:
        logger.warning(f"Could not probe video dimensions: {e}")
    return 1920, 1080  # assume landscape as fallback


def is_vertical(width: int, height: int) -> bool:
    """Return True if video is already in 9:16 (portrait) ratio."""
    return height >= width * 1.5


def format_to_vertical(
    input_path:  Path,
    output_path: Path,
    mode:        str = "blur_pad",   # "original" | "crop_center" | "blur_pad"
    hw_device:   Optional[str] = None
) -> bool:
    """
    Convert a clip to 9:16 vertical format.

    Args:
        input_path:  Source clip MP4 (any aspect ratio)
        output_path: Output MP4 (9:16, 1080x1920)
        mode:        Conversion mode — see module docstring
        hw_device:   VAAPI device path (e.g. /dev/dri/renderD128), optional

    Returns:
        True on success, False on failure.
    """
    w, h = get_video_dimensions(input_path)

    # If source is already 9:16, skip conversion (just copy)
    if mode == "original" or is_vertical(w, h):
        if input_path != output_path:
            import shutil
            shutil.copy2(str(input_path), str(output_path))
        return True

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "crop_center":
        vf = _build_crop_center_filter()
    else:  # blur_pad (default)
        vf = _build_blur_pad_filter()

    # Always use software encode for filter-heavy operations
    # (VAAPI complex filter graph requires hwupload/hwdownload wrapping)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"Video format failed: {result.stderr[-500:]}")
            return False
        logger.info(f"Formatted to 9:16: {output_path} (mode={mode})")
        return True
    except subprocess.TimeoutExpired:
        logger.error("Video format timed out after 300s")
        return False
    except Exception as e:
        logger.error(f"Video format exception: {e}")
        return False


def _build_crop_center_filter() -> str:
    """
    Crop the center column of the source to 9:16, then scale to 1080x1920.
    
    Crop formula: take a vertical strip from the horizontal center.
    crop=ih*(9/16):ih  →  crop width = (source height × 9/16), height = source height
    Then scale result to 1080x1920.
    """
    return (
        f"crop=ih*9/16:ih,"
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:flags=lanczos"
    )


def _build_blur_pad_filter() -> str:
    """
    Blur pad filter:
    1. Scale source to fill 1080x1920 height (letterbox fit) for the foreground
    2. Scale source to fill 1080x1920 width (pan/crop fill) for the background
    3. Apply strong gaussian blur to background
    4. Overlay sharp foreground centered on blurred background
    
    Result: No content is cropped. Sides are filled with tasteful blurred background.
    This is the standard style used by MrBeast, podcast clips, and brand Reels.
    """
    return (
        # [0:v] split into two streams: [fg] and [bg]
        f"split[fg][bg];"
        # Background: scale to fill full 1080×1920 (may crop), blur heavily
        f"[bg]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},"
        f"gblur=sigma=25[blurred];"
        # Foreground: scale to fit within 1080×1920 (letterbox), keep aspect ratio
        f"[fg]scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease[sharp];"
        # Overlay sharp centered on blurred background
        f"[blurred][sharp]overlay=(W-w)/2:(H-h)/2"
    )
