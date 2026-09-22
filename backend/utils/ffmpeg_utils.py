"""
FFmpeg Executable path resolution utility

Priority order: 
1) Environment variables have higher precedence over system PATH when resolving commands or paths for dependencies such as `ffmpeg` and `ffprobe`. This allows users to override the default location with custom versions, ensuring compatibility and overriding the bundled defaults if necessary. AUTOCLIP_FFMPEG_PATH / AUTOCLIP_FFPROBE_PATH / FFMPEG_PATH / FFPROBE_PATH
2) Command name found in system PATH ffmpeg/ffprobe

Purpose: Provide unified access for all backend caller points ffmpeg/ffprobe Path, making it easy to bundle a pre-built binary in desktop installers for zero-dependency use. 
"""

import os
import shutil
from typing import Optional


def _resolve_from_env(var_names: list[str]) -> Optional[str]:
    for var in var_names:
        value = os.getenv(var)
        if value and os.path.exists(value):
            return value
    return None


def get_ffmpeg_path() -> str:
    """Return path to ffmpeg executable (or command name)). """
    # Environment variables take priority
    env_path = _resolve_from_env([
        "AUTOCLIP_FFMPEG_PATH",
        "FFMPEG_PATH",
    ])
    if env_path:
        return env_path

    # System PATH
    which = shutil.which("ffmpeg")
    if which:
        return which

    # Return command name as fallback (may still fail but preserve compatibility)
    return "ffmpeg"


def get_ffprobe_path() -> str:
    """Return path to ffprobe executable (or command name)). """
    # Environment variables take priority
    env_path = _resolve_from_env([
        "AUTOCLIP_FFPROBE_PATH",
        "FFPROBE_PATH",
    ])
    if env_path:
        return env_path

    # System PATH
    which = shutil.which("ffprobe")
    if which:
        return which

    # Return command name as fallback
    return "ffprobe"


