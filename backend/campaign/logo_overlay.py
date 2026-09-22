"""
Apply a brand logo watermark to a video clip using FFmpeg.
"""
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

POSITION_MAP = {
    "top_right":    "W-w-20:20",
    "top_left":     "20:20",
    "bottom_right": "W-w-20:H-h-20",
    "bottom_left":  "20:H-h-20",
}

def apply_logo_overlay(
    video_path:    Path,
    logo_path:     Path,
    output_path:   Path,
    position:      str   = "top_right",
    scale_percent: float = 0.12,
    hw_device:     Optional[str] = None    # e.g. "/dev/dri/renderD128" for VAAPI
) -> bool:
    """
    Burn a brand logo into a video using FFmpeg overlay filter.
    
    Args:
        video_path:    Input clip MP4
        logo_path:     Logo file (PNG with transparency preferred)
        output_path:   Output MP4 with logo burned in
        position:      One of: top_right, top_left, bottom_right, bottom_left
        scale_percent: Logo width as fraction of video width (0.12 = 12%)
        hw_device:     VAAPI device path for hardware encoding (optional)
    
    Returns:
        True on success, False on failure
    """
    xy = POSITION_MAP.get(position, POSITION_MAP["top_right"])
    
    # Scale logo to scale_percent of video width, keep aspect ratio
    logo_scale = f"scale=iw*{scale_percent}:-1"
    
    # Handle logo transparency: PNG alpha → use as-is; JPEG → add 80% opacity
    logo_suffix = logo_path.suffix.lower()
    if logo_suffix in ('.jpg', '.jpeg'):
        logo_filter = f"[1:v]{logo_scale},format=rgba,colorchannelmixer=aa=0.8[logo]"
    else:
        logo_filter = f"[1:v]{logo_scale}[logo]"
    
    overlay_filter = f"{logo_filter};[0:v][logo]overlay={xy}[out]"
    
    # Build FFmpeg command
    # Software encode (safe fallback):
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(logo_path),
        "-filter_complex", overlay_filter,
        "-map", "[out]",
        "-map", "0:a?",           # copy audio if present
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "copy",
        str(output_path)
    ]
    
    # VAAPI hardware encode (if device available):
    # Note: VAAPI overlay is complex; use software encode for logo overlay
    # (logo overlay is a one-time operation, CPU cost is acceptable)
    
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            logger.error(f"Logo overlay failed: {result.stderr[-500:]}")
            return False
        logger.info(f"Logo overlay applied: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Logo overlay exception: {e}")
        return False


def download_logo(logo_url: str, dest_dir: Path) -> Optional[Path]:
    """
    Download logo from URL (Google Drive or direct URL).
    Returns local path, or None on failure.
    """
    import requests
    import re
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert Google Drive share link to direct download
    drive_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', logo_url)
    if drive_match:
        file_id   = drive_match.group(1)
        logo_url  = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    try:
        resp = requests.get(logo_url, stream=True, timeout=30)
        resp.raise_for_status()
        
        # Detect extension from content-type
        content_type = resp.headers.get('content-type', 'image/png')
        ext = '.png' if 'png' in content_type else '.jpg'
        
        dest_path = dest_dir / f"logo{ext}"
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Logo downloaded: {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"Logo download failed from {logo_url}: {e}")
        return None
