"""
Whisper Runtime management (desktop mode, on-demand installation)

Desktop installer does not include Whisper by default (runtime + Model files can be large, no need to make all users download them. Users can set up
where you can decide for yourself whether to install and which model to download. The backend uses faster-whisper (CTranslate2, no dependencies
PyTorch, During runtime ~200-400MB, 3-4 times faster than the official whisper, cross-platform). 

Design considerations: 
- Installed to「Writable user directory」`<data_dir>/whisper-runtime`, Not within .app package
  (/Applications Usually read-only, and writing will break code signature). 
- Used as a single-package solution「Currently running portable backend Python」(sys.executable) Use the actual installation result to override during initialization. 
- Model cache location `<data_dir>/whisper-models`(Closing through HF_HOME). 
- All operations on mlx_whisper / huggingface_hub Imports are delayed until inside functions to avoid build time
  Dependency scans will cause packaging to fail if they are missing dependencies. 
"""

import os
import sys
import shutil
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# The runtime package to install (faster-whisper with ctranspose2, onnxruntime, av, huggingface_hub, etc.),
# Without PyTorch)
WHISPER_PACKAGES = ["faster-whisper"]
# Core runtime module (used to detect if installed)
WHISPER_IMPORT_NAME = "faster_whisper"


def _data_dir() -> Path:
    try:
        from backend.core.desktop_config import get_desktop_data_dir
        return Path(get_desktop_data_dir())
    except Exception:
        return Path(os.getenv("AUTOCLIP_DATA_DIR", str(Path.home() / "Library/Application Support/AutoClip")))


def get_install_dir() -> Path:
    d = _data_dir() / "whisper-runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_models_dir() -> Path:
    d = _data_dir() / "whisper-models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_on_path() -> None:
    """Add the runtime directory to sys.path and funnel the model cache directory through a single interface HF_HOME. """
    install_dir = str(get_install_dir())
    if install_dir not in sys.path:
        sys.path.insert(0, install_dir)
    # All models cached in the data directory for easy management/uninstallation
    os.environ.setdefault("HF_HOME", str(get_models_dir()))
    # on mlx-whisper to decode audio files, use ffmpeg: add the ffmpeg binary directory to PATH
    ffmpeg_path = os.getenv("AUTOCLIP_FFMPEG_PATH")
    if ffmpeg_path:
        ffmpeg_dir = str(Path(ffmpeg_path).parent)
        if ffmpeg_dir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def is_installed() -> bool:
    """Whether the runtime is ready (mlwhisper can be imported)). """
    ensure_on_path()
    try:
        import importlib.util
        return importlib.util.find_spec(WHISPER_IMPORT_NAME) is not None
    except Exception:
        return False


# ---- Runtime Status (for front-end polling) ---
_state_lock = threading.Lock()
_state: Dict[str, Any] = {
    "status": "unknown",   # not_installed | installing | installed | error
    "progress": 0,         # Coarse-grained percentage
    "message": "",
    "log_tail": "",
}


def _set_state(**kw) -> None:
    with _state_lock:
        _state.update(kw)


def get_status() -> Dict[str, Any]:
    with _state_lock:
        st = dict(_state)
    # If not installing, overwrite with actual detection results
    if st["status"] not in ("installing",):
        st["status"] = "installed" if is_installed() else "not_installed"
        if st["status"] == "installed":
            st["progress"] = 100
    st["platform_supported"] = True  # faster-whisper Cross-platform
    st["packages"] = WHISPER_PACKAGES
    return st


def _do_install(index_url: Optional[str]) -> None:
    install_dir = get_install_dir()
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--upgrade",
        "--target", str(install_dir),
        *WHISPER_PACKAGES,
    ]
    if index_url:
        cmd += ["--index-url", index_url]
    logger.info(f"Starting to install Whisper runtime: {' '.join(cmd)}")
    _set_state(status="installing", progress=5, message="Preparing installation…", log_tail="")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        lines: list[str] = []
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            lines.append(line)
            lines[:] = lines[-40:]
            # Granular progress: based on stages from pip phase words, purely aesthetic
            low = line.lower()
            if low.startswith("collecting") or "downloading" in low:
                _bump_progress(min_v=10, max_v=70, message=line)
            elif "installing collected packages" in low or "building" in low:
                _bump_progress(min_v=70, max_v=95, message="Installing dependencies…")
            _set_state(log_tail="\n".join(lines[-12:]))
        proc.wait()
        if proc.returncode == 0 and is_installed():
            _set_state(status="installed", progress=100, message="Installation complete")
            logger.info("Whisper Runtime installation completed")
        else:
            _set_state(status="error", message=f"Installation failed (pip exit code {proc.returncode})")
            logger.error(f"Whisper Runtime installation failed, pip exit code {proc.returncode}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to install Whisper runtime: {e}", exc_info=True)
        _set_state(status="error", message=f"Installation error: {e}")


def _bump_progress(min_v: int, max_v: int, message: str) -> None:
    with _state_lock:
        cur = _state.get("progress", 0)
        _state["progress"] = max(min_v, min(max_v, cur + 2))
        _state["message"] = message


def start_install(index_url: Optional[str] = None) -> Dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"started": False, "message": "Installation in progress"}
    if is_installed():
        _set_state(status="installed", progress=100, message="Installed successfully")
        return {"started": False, "message": "Installed successfully"}
    # Default to the pip source in environment variables (building scripts/desktop default Tsinghua), otherwise PyPI
    idx = index_url or os.getenv("PIP_INDEX_URL")
    threading.Thread(target=_do_install, args=(idx,), name="whisper-install", daemon=True).start()
    return {"started": True, "message": "Installation started"}


def uninstall() -> Dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"success": False, "message": "Already installing, cannot uninstall"}
    install_dir = get_install_dir()
    try:
        shutil.rmtree(install_dir, ignore_errors=True)
        # Remove from sys.modules to avoid this process still being able to import
        for mod in [m for m in list(sys.modules) if m.startswith("faster_whisper") or m.startswith("ctranslate2")]:
            sys.modules.pop(mod, None)
        p = str(install_dir)
        if p in sys.path:
            sys.path.remove(p)
        _set_state(status="not_installed", progress=0, message="Uninstalled successfully")
        return {"success": True, "message": "Whisper runtime has been uninstalled"}
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to uninstall Whisper runtime: {e}")
        return {"success": False, "message": str(e)}
