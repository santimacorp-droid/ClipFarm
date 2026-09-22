"""
Simplified progress service - fixed stage + Fixed weight
Based on your "do simple and steady" proposal
"""

import time
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
import sqlite3
import threading
import os
try:
    import redis  # Optional dependency
except Exception:
    redis = None

logger = logging.getLogger(__name__)

# Fixed stage definition - adjust according to your project specifics
STAGES: List[Tuple[str, int]] = [
    ("INGEST", 10),        # Download/Prerequisites
    ("SUBTITLE", 15),      # Captions/Subtitles/Alignment
    ("ANALYZE", 20),       # Semantic analysis/Outline
    ("HIGHLIGHT", 25),     # Fragment positioning/Scoring
    ("EXPORT", 20),        # Export/Encapsulation
    ("DONE", 10),          # Validation/Archive
]

# Stage weight mapping
WEIGHTS = {name: w for name, w in STAGES}
# Phase sequence
ORDER = [name for name, _ in STAGES]

class ProgressStore:
    def save(self, project_id: str, stage: str, percent: int, message: str, ts: int):
        raise NotImplementedError

    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def delete(self, project_id: str):
        raise NotImplementedError

    def get_many(self, project_ids: List[str]) -> List[Dict[str, Any]]:
        return [s for pid in project_ids if (s := self.get(pid))]


class RedisProgressStore(ProgressStore):
    def __init__(self, redis_client):
        self.r = redis_client

    def save(self, project_id: str, stage: str, percent: int, message: str, ts: int):
        self.r.hset(f"progress:project:{project_id}", mapping={
            "stage": stage,
            "percent": str(percent),
            "message": message,
            "ts": str(ts)
        })
        payload = {"project_id": project_id, "stage": stage, "percent": percent, "message": message, "ts": ts}
        try:
            self.r.publish(f"progress:project:{project_id}", json.dumps(payload))
        except Exception:
            pass

    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        h = self.r.hgetall(f"progress:project:{project_id}")
        if not h:
            return None
        return {
            "project_id": project_id,
            "stage": h.get("stage", ""),
            "percent": int(h.get("percent", 0)),
            "message": h.get("message", ""),
            "ts": int(h.get("ts", 0))
        }

    def delete(self, project_id: str):
        self.r.delete(f"progress:project:{project_id}")


class SqliteProgressStore(ProgressStore):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS progress_snapshots (
                project_id TEXT PRIMARY KEY,
                stage TEXT,
                percent INTEGER,
                message TEXT,
                ts INTEGER
            )
            """
        )
        self._conn.commit()

    def save(self, project_id: str, stage: str, percent: int, message: str, ts: int):
        with self._lock:
            self._conn.execute(
                "REPLACE INTO progress_snapshots (project_id, stage, percent, message, ts) VALUES (?, ?, ?, ?, ?)",
                (project_id, stage, int(percent), message, int(ts))
            )
            self._conn.commit()

    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT stage, percent, message, ts FROM progress_snapshots WHERE project_id = ?",
                (project_id,)
            )
            row = cur.fetchone()
        if not row:
            return None
        stage, percent, message, ts = row
        return {
            "project_id": project_id,
            "stage": stage or "",
            "percent": int(percent or 0),
            "message": message or "",
            "ts": int(ts or 0)
        }

    def delete(self, project_id: str):
        with self._lock:
            self._conn.execute("DELETE FROM progress_snapshots WHERE project_id = ?", (project_id,))
            self._conn.commit()

    def get_many(self, project_ids: List[str]) -> List[Dict[str, Any]]:
        if not project_ids:
            return []
        placeholders = ",".join(["?"] * len(project_ids))
        with self._lock:
            cur = self._conn.execute(
                f"SELECT project_id, stage, percent, message, ts FROM progress_snapshots WHERE project_id IN ({placeholders})",
                project_ids
            )
            rows = cur.fetchall()
        results = []
        for pid, stage, percent, message, ts in rows:
            results.append({
                "project_id": pid,
                "stage": stage or "",
                "percent": int(percent or 0),
                "message": message or "",
                "ts": int(ts or 0)
            })
        return results


# Storage selection: Desktop mode enforces SQLite; Server mode prefers Redis, with automatic downgrade to SQLite if failed
store: ProgressStore
try:
    from backend.core.desktop_config import is_desktop_mode, get_desktop_paths
    if is_desktop_mode():
        paths = get_desktop_paths()
        db_file = os.path.join(str(paths.data_dir), "progress.db")
        store = SqliteProgressStore(db_file)
        logger.info(f"SQLite progress storage used in desktop mode: {db_file}")
    else:
        if redis is None:
            raise RuntimeError("redis Not installed")
        # Retrieve Redis URL from environment variables, defaulting to local address
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        r_client = redis.Redis.from_url(redis_url, decode_responses=True)
        r_client.ping()
        store = RedisProgressStore(r_client)
        logger.info("ServerRedis progress storage used in mode")
except Exception as e:
    # Automatic fallback to SQLite
    try:
        # Prefer desktop data directory; fallback to project root data directory if unavailable
        db_file = None
        try:
            from backend.core.desktop_config import get_desktop_paths
            db_file = os.path.join(str(get_desktop_paths().data_dir), "progress.db")
        except Exception:
            from pathlib import Path
            db_file = str((Path(__file__).parent.parent.parent / 'data' / 'progress.db').resolve())
        store = SqliteProgressStore(db_file)
        logger.warning(f"RedisFalls back to SQLite progress storage if Redis is unavailable or not installed: {db_file}, Reason: {e}")
    except Exception as e2:
        logger.error(f"Failed to initialize progress store: {e2}")
        store = None


def compute_percent(stage: str, subpercent: Optional[float] = None) -> int:
    """
    Calculates corresponding percentage for stage
    
    Args:
        stage: Current stage name
        subpercent: Sub-progress percentage (0-100), optional
        
    Returns:
        Overall progress percentage (0-100)
    """
    # Accumulate previous phase weight
    done = 0
    for s in ORDER:
        if s == stage:
            break
        done += WEIGHTS[s]
    
    # Current stage
    cur = WEIGHTS.get(stage, 0)
    
    if subpercent is None:
        # Upon stage switching, displays from the current stage start
        return min(100, done + cur) if stage == "DONE" else min(99, done)
    else:
        # With sub-progress, linearly converted by weight
        subpercent = max(0, min(100, subpercent))
        return min(99, done + int(cur * subpercent / 100))


def emit_progress(project_id: str, stage: str, message: str = "", subpercent: Optional[float] = None):
    """
    Send progress event
    
    Args:
        project_id: ProjectID
        stage: Current stage
        message: Progress message
        subpercent: Sub-progress percentage, optional
    """
    if not store:
        logger.warning("Progress store not initialized, skips progress sending")
        return
        
    percent = compute_percent(stage, subpercent)
    payload = {
        "project_id": project_id,
        "stage": stage,
        "percent": percent,
        "message": message,
        "ts": int(time.time())
    }
    
    try:
        store.save(project_id, stage, percent, message, payload["ts"])
        logger.info(f"Progress event sent: {project_id} - {stage} ({percent}%) - {message}")
    except Exception as e:
        logger.error(f"Sending progress event failed: {e}")


def get_progress_snapshot(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Gets project progress snapshot
    
    Args:
        project_id: ProjectID
        
    Returns:
        Progress snapshot data, returns nothing if it doesn't existNone
    """
    if not store:
        return None
        
    try:
        return store.get(project_id)
    except Exception as e:
        logger.error(f"Failed to retrieve progress snapshot: {e}")
        return None


def get_multiple_progress_snapshots(project_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Batch retrieves multiple project progress snapshots
    
    Args:
        project_ids: List of project IDs
        
    Returns:
        Progress snapshot list
    """
    if not store:
        return []
    try:
        return store.get_many(project_ids)
    except Exception as e:
        logger.error(f"Batch retrieving progress snapshots failed: {e}")
        return []


def clear_progress(project_id: str):
    """
    Clear project progress data
    
    Args:
        project_id: ProjectID
    """
    if not store:
        return
    try:
        store.delete(project_id)
        logger.info(f"Cleared project progress data: {project_id}")
    except Exception as e:
        logger.error(f"Failed to clear progress data: {e}")


# Stage name mapping (for display)
STAGE_NAMES = {
    "INGEST": "Material preparation",
    "SUBTITLE": "Subtitle processing", 
    "ANALYZE": "Content analysis",
    "HIGHLIGHT": "Fragment positioning",
    "EXPORT": "Video export",
    "DONE": "Processing complete"
}

def get_stage_display_name(stage: str) -> str:
    """Gets display name of stage"""
    return STAGE_NAMES.get(stage, stage)
