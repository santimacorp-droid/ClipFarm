"""
Unified path management tool
Resolve inconsistent path construction within the project
"""

import os
import sys
from pathlib import Path
from typing import Optional

DESKTOP_TRUE_VALUES = {"1", "true", "yes", "on"}


def is_desktop_mode() -> bool:
    """Determine if current execution is in desktop runtime mode"""
    return (
        os.getenv("CLIPFARM_DESKTOP_MODE", "").lower() in DESKTOP_TRUE_VALUES
        or os.getenv("AUTOCLIP_DESKTOP_MODE", "").lower() in DESKTOP_TRUE_VALUES
        or os.getenv("AUTOCLIP_MODE", "").lower() in {"desktop", "standalone"}
        or os.getenv("CLIPFARM_MODE", "").lower() in {"desktop", "standalone"}
        or os.getenv("CLIPFARM_STANDALONE", "").lower() in DESKTOP_TRUE_VALUES
    )

def get_default_app_data_dir() -> Path:
    """Get platform-standard user application data directory across Windows, macOS, and Linux."""
    configured = os.getenv("CLIPFARM_APP_DIR") or os.getenv("AUTOCLIP_APP_DIR")
    if configured:
        return Path(configured).expanduser()

    if sys.platform == "win32":
        appdata = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if appdata:
            return Path(appdata) / "ClipFarm"
        return Path.home() / "AppData" / "Roaming" / "ClipFarm"
    elif sys.platform == "darwin":
        old_dir = Path.home() / "Library" / "Application Support" / "AutoClip"
        new_dir = Path.home() / "Library" / "Application Support" / "ClipFarm"
        if old_dir.exists() and not new_dir.exists():
            return old_dir
        return new_dir
    else:
        # Linux / BSD / Unix (XDG standard)
        xdg = os.getenv("XDG_DATA_HOME")
        if xdg:
            return Path(xdg) / "clipfarm"
        return Path.home() / ".local" / "share" / "clipfarm"

def get_project_root() -> Path:
    """
    Get project root directory
    Search upward from the backend directory until finding a directory containing both frontend and backend
    """
    current_path = Path(__file__).parent  # backend/core/
    
    # Search upward to find project root directory
    while current_path.parent != current_path:  # Did not reach root directory
        if (current_path.parent / "frontend").exists() and (current_path.parent / "backend").exists():
            return current_path.parent
        current_path = current_path.parent
    
    # If not found, use default path
    return Path(__file__).parent.parent.parent

def get_data_directory() -> Path:
    """Get data directory with automatic fallback to user home directory if root is read-only"""
    configured_data_dir = os.getenv("CLIPFARM_DATA_DIR") or os.getenv("AUTOCLIP_DATA_DIR")
    if configured_data_dir:
        data_dir = Path(configured_data_dir).expanduser()
    elif is_desktop_mode():
        data_dir = get_default_app_data_dir()
    else:
        root_data = get_project_root() / "data"
        try:
            root_data.mkdir(parents=True, exist_ok=True)
            test_file = root_data / ".perm_check"
            test_file.touch()
            test_file.unlink()
            data_dir = root_data
        except (PermissionError, OSError):
            data_dir = get_default_app_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_projects_directory() -> Path:
    """Get project directory"""
    projects_dir = get_data_directory() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir

def get_output_directory() -> Path:
    """Get output directory"""
    output_dir = get_data_directory() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def get_project_directory(project_id: str) -> Path:
    """Get project directory"""
    project_dir = get_projects_directory() / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir

def get_project_raw_directory(project_id: str) -> Path:
    """Get original files directory for the project"""
    raw_dir = get_project_directory(project_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir

def get_project_output_directory(project_id: str) -> Path:
    """Get project output directory"""
    output_dir = get_project_directory(project_id) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def get_clips_directory() -> Path:
    """Get slice directory"""
    clips_dir = get_output_directory() / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    return clips_dir

def get_collections_directory() -> Path:
    """Get collection directory"""
    collections_dir = get_output_directory() / "collections"
    collections_dir.mkdir(parents=True, exist_ok=True)
    return collections_dir

def get_metadata_directory() -> Path:
    """Get metadata directory for the project"""
    metadata_dir = get_output_directory() / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    return metadata_dir

def get_settings_file_path() -> Path:
    """Get settings file path"""
    return get_data_directory() / "settings.json"

def get_uploads_directory() -> Path:
    """Get upload directory"""
    uploads_dir = get_data_directory() / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir

def get_temp_directory() -> Path:
    """Get temporary directory"""
    temp_dir = get_data_directory() / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

def ensure_directory_exists(path: Path) -> Path:
    """Ensure directory exists"""
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_video_file_path(project_id: str, filename: str) -> Path:
    """Get video file path for the project"""
    return get_project_raw_directory(project_id) / filename

def get_srt_file_path(project_id: str, filename: str) -> Path:
    """Get SRT file path for the project"""
    return get_project_raw_directory(project_id) / filename

def get_clip_file_path(clip_id: str, title: str) -> Path:
    """Get slice file path"""
    # Clean filename by removing special characters
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    return get_clips_directory() / f"{clip_id}_{safe_title}.mp4"

def get_collection_file_path(collection_id: str, title: str) -> Path:
    """Get collection file path"""
    # Clean filename by removing special characters
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    return get_collections_directory() / f"{collection_id}_{safe_title}.mp4"

def get_metadata_file_path(project_id: str) -> Path:
    """Get metadata file path for the project"""
    return get_metadata_directory() / f"{project_id}_metadata.json"

def get_log_file_path() -> Path:
    """Get log file path"""
    configured_log_file = os.getenv("LOG_FILE")
    if configured_log_file:
        log_file = Path(configured_log_file).expanduser()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        return log_file
    logs_dir = get_data_directory() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "backend.log"

def get_cache_directory() -> Path:
    """Get cache directory"""
    cache_dir = get_data_directory() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def get_backup_directory() -> Path:
    """Get backup directory path"""
    backup_dir = get_data_directory() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def cleanup_temp_files(max_age_hours: int = 24):
    """Clean temporary files"""
    import time
    temp_dir = get_temp_directory()
    current_time = time.time()
    
    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            file_age = current_time - file_path.stat().st_mtime
            if file_age > (max_age_hours * 3600):
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"Failed to clean temporary files: {file_path}, Error: {e}")

def validate_file_path(file_path: Path) -> bool:
    """Validate file path for safety"""
    try:
        # Check whether a path is within the allowed directory
        allowed_dirs = [
            get_data_directory(),
            get_output_directory(),
            get_project_root()
        ]
        
        file_path = file_path.resolve()
        return any(file_path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs)
    except Exception:
        return False


def find_clip_video_file(
    project_id: Optional[str],
    clip_id: str,
    clip_obj=None,
    db=None
):
    """
    Locates the video file for a clip with extensive fallbacks:
    - Matches clip by UUID, integer metadata ID (e.g. '1', '2'), or title
    - Handles filename sanitization differences (hyphens vs underscores, special characters)
    - Automatically updates stale or incorrect database video_path
    Returns tuple: (Optional[Path], Optional[Clip])
    """
    try:
        # 1. Attempt to find the Clip database object if not passed
        if clip_obj is None and db is not None:
            try:
                from backend.models.clip import Clip
                # Query by primary key UUID
                clip_obj = db.query(Clip).filter(Clip.id == clip_id).first()
                if not clip_obj and project_id:
                    # Query all clips for this project
                    project_clips = db.query(Clip).filter(Clip.project_id == project_id).all()
                    for c in project_clips:
                        meta_id = (getattr(c, 'clip_metadata', None) or {}).get('id')
                        if meta_id is not None and str(meta_id) == str(clip_id):
                            clip_obj = c
                            break
                    if not clip_obj:
                        for c in project_clips:
                            if getattr(c, 'title', None) == clip_id or getattr(c, 'generated_title', None) == clip_id:
                                clip_obj = c
                                break
                    if not clip_obj and str(clip_id).isdigit():
                        idx = int(clip_id)
                        if 1 <= idx <= len(project_clips):
                            sorted_clips = sorted(
                                project_clips,
                                key=lambda x: (getattr(x, 'start_time', 0) or 0, str(getattr(x, 'created_at', '')))
                            )
                            clip_obj = sorted_clips[idx - 1]
            except Exception:
                pass

        # If clip_obj has an existing, valid file on disk, return it
        if clip_obj and getattr(clip_obj, 'video_path', None):
            p = Path(clip_obj.video_path)
            if p.exists() and p.is_file():
                return p, clip_obj

        # 2. Build candidate directories to inspect across all possible data roots
        target_project_id = project_id or (str(clip_obj.project_id) if clip_obj and getattr(clip_obj, 'project_id', None) else None)
        candidate_dirs = []
        possible_roots = list(dict.fromkeys([get_data_directory(), get_default_app_data_dir(), get_project_root() / "data"]))
        for r in possible_roots:
            if target_project_id:
                proj_dir = r / "projects" / str(target_project_id)
                candidate_dirs.extend([
                    proj_dir / "output" / "clips",
                    proj_dir / "output",
                    proj_dir
                ])
            candidate_dirs.extend([
                r / "output" / "clips",
                r / "clips"
            ])

        # 3. Search for video files
        orig_id = None
        if clip_obj:
            orig_id = (getattr(clip_obj, 'clip_metadata', None) or {}).get('id')

        norm_names_to_match = set()
        if clip_obj:
            if getattr(clip_obj, 'title', None):
                norm_names_to_match.add("".join(c.lower() for c in clip_obj.title if c.isalnum()))
            if getattr(clip_obj, 'generated_title', None):
                norm_names_to_match.add("".join(c.lower() for c in clip_obj.generated_title if c.isalnum()))
            if getattr(clip_obj, 'video_path', None):
                norm_names_to_match.add("".join(c.lower() for c in Path(clip_obj.video_path).stem if c.isalnum()))

        for d in candidate_dirs:
            if not d.exists():
                continue

            mp4_files = list(d.glob("*.mp4"))
            if not mp4_files:
                continue

            # Check exact or prefix matches
            # A: clip_id prefix or exact
            for f in mp4_files:
                if f.stem == clip_id or f.stem.startswith(f"{clip_id}_"):
                    _update_clip_path(clip_obj, f, db)
                    return f, clip_obj

            # B: clip_obj UUID prefix
            if clip_obj and getattr(clip_obj, 'id', None):
                for f in mp4_files:
                    if f.stem == str(clip_obj.id) or f.stem.startswith(f"{clip_obj.id}_"):
                        _update_clip_path(clip_obj, f, db)
                        return f, clip_obj

            # C: original pipeline index ID (e.g. 1, 2, 6)
            if orig_id is not None:
                for f in mp4_files:
                    if f.stem.startswith(f"{orig_id}_"):
                        _update_clip_path(clip_obj, f, db)
                        return f, clip_obj

            # D: digit clip_id prefix
            if str(clip_id).isdigit():
                for f in mp4_files:
                    if f.stem.startswith(f"{clip_id}_"):
                        _update_clip_path(clip_obj, f, db)
                        return f, clip_obj

            # E: normalized alphanumeric name matching
            for norm_target in norm_names_to_match:
                if not norm_target:
                    continue
                for f in mp4_files:
                    norm_file = "".join(c.lower() for c in f.stem if c.isalnum())
                    if norm_target in norm_file or norm_file in norm_target:
                        _update_clip_path(clip_obj, f, db)
                        return f, clip_obj

        return None, clip_obj
    except Exception as e:
        return None, clip_obj


def _update_clip_path(clip_obj, file_path: Path, db):
    """Helper to persist resolved video path back to database."""
    if clip_obj and db:
        try:
            clip_obj.video_path = str(file_path)
            db.commit()
        except Exception:
            pass


def find_collection_video_file(
    project_id: Optional[str],
    collection_id: str,
    collection_obj=None,
    db=None
):
    """
    Locates the video file for a collection with fallbacks.
    Returns tuple: (Optional[Path], Optional[Collection])
    """
    try:
        if collection_obj is None and db is not None:
            try:
                from backend.models.collection import Collection
                collection_obj = db.query(Collection).filter(Collection.id == collection_id).first()
                if not collection_obj and project_id:
                    project_collections = db.query(Collection).filter(Collection.project_id == project_id).all()
                    for col in project_collections:
                        if getattr(col, 'name', None) == collection_id or str(getattr(col, 'id', None)) == str(collection_id):
                            collection_obj = col
                            break
            except Exception:
                pass

        if collection_obj and getattr(collection_obj, 'export_path', None):
            p = Path(collection_obj.export_path)
            if p.exists() and p.is_file():
                return p, collection_obj

        target_project_id = project_id or (str(collection_obj.project_id) if collection_obj and getattr(collection_obj, 'project_id', None) else None)
        candidate_dirs = []
        possible_roots = list(dict.fromkeys([get_data_directory(), get_default_app_data_dir(), get_project_root() / "data"]))
        for r in possible_roots:
            if target_project_id:
                proj_dir = r / "projects" / str(target_project_id)
                candidate_dirs.extend([
                    proj_dir / "output" / "collections",
                    proj_dir / "output",
                    proj_dir / "export",
                    proj_dir
                ])
            candidate_dirs.extend([
                r / "output" / "collections",
                r / "collections"
            ])

        norm_names_to_match = set()
        if collection_id:
            norm_names_to_match.add("".join(c.lower() for c in str(collection_id) if c.isalnum()))
        if collection_obj:
            if getattr(collection_obj, 'name', None):
                norm_names_to_match.add("".join(c.lower() for c in collection_obj.name if c.isalnum()))
            if getattr(collection_obj, 'export_path', None):
                norm_names_to_match.add("".join(c.lower() for c in Path(collection_obj.export_path).stem if c.isalnum()))

        for d in candidate_dirs:
            if not d.exists():
                continue
            mp4_files = list(d.glob("*.mp4"))
            for f in mp4_files:
                norm_f = "".join(c.lower() for c in f.stem if c.isalnum())
                for norm_target in norm_names_to_match:
                    if norm_target and (norm_target in norm_f or norm_f in norm_target):
                        if collection_obj and db:
                            try:
                                collection_obj.export_path = str(f)
                                db.commit()
                            except Exception:
                                pass
                        return f, collection_obj

            if len(mp4_files) == 1 and ("collections" in str(d)):
                f = mp4_files[0]
                if collection_obj and db:
                    try:
                        collection_obj.export_path = str(f)
                        db.commit()
                    except Exception:
                        pass
                return f, collection_obj

        return None, collection_obj
    except Exception:
        return None, collection_obj


def reveal_in_file_manager(target_path: Path) -> bool:
    """
    Open native file explorer and highlight/reveal the target file or directory.
    Cross-platform support:
      - Windows: explorer.exe /select,path (or explorer.exe folder)
      - macOS: open -R path (or open folder)
      - Linux: xdg-open folder (opens native file manager such as Nautilus, Dolphin, Thunar)
    """
    import logging
    import platform
    import subprocess

    log = logging.getLogger(__name__)
    try:
        target = Path(target_path).resolve()
        if not target.exists():
            target = target.parent
        if not target.exists():
            log.warning(f"Path does not exist to reveal: {target_path}")
            return False

        sys_name = platform.system()
        if sys_name == "Windows":
            if target.is_file():
                subprocess.Popen(["explorer.exe", f"/select,{str(target)}"])
            else:
                subprocess.Popen(["explorer.exe", str(target)])
            return True
        elif sys_name == "Darwin":
            if target.is_file():
                subprocess.Popen(["open", "-R", str(target)])
            else:
                subprocess.Popen(["open", str(target)])
            return True
        else:
            # Linux / Unix
            folder = target if target.is_dir() else target.parent
            subprocess.Popen(["xdg-open", str(folder)])
            return True
    except Exception as e:
        log.warning(f"Failed to reveal in file manager: {e}")
        return False

