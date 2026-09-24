"""
ProgressTracker — Granular pipeline progress with heartbeat and live logs.

Usage:
    tracker = ProgressTracker(project_id, task_id)
    tracker.set_step(1, "Finding Key Moments", total_steps=6)
    tracker.set_substep("Chunk 1 of 4 · qwen3.8-max", current=1, total=4)
    tracker.heartbeat()   # call every few seconds during long operations
    tracker.log("Found 4 moments in chunk 2")
    tracker.complete()
"""

import time
import threading
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Step definitions — human-readable names for each pipeline step
STEP_LABELS = {
    0: "Transcribing Audio",
    1: "Finding Key Moments",
    2: "Setting Timestamps",
    3: "Scoring Clips",
    4: "Generating Titles",
    5: "Selecting Best Clips",
    6: "Cutting Video Clips",
    7: "Finalizing",
}

TOTAL_PIPELINE_STEPS = 6   # steps 1–6


@dataclass
class ProgressState:
    project_id: str
    task_id: str = ""
    
    # Step-level
    current_step: int = 0
    total_steps: int = TOTAL_PIPELINE_STEPS
    step_name: str = "Preparing"
    step_percent: float = 0.0          # 0.0–100.0 within current step
    overall_percent: float = 0.0       # 0.0–100.0 across all steps
    
    # Sub-step
    substep: str = ""                  # e.g. "Chunk 3 of 8 · qwen3.8-max"
    substep_current: int = 0
    substep_total: int = 0
    
    # Alive indicator
    is_alive: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_interval: float = 3.0    # seconds
    
    # Timing
    started_at: float = field(default_factory=time.time)
    step_started_at: float = field(default_factory=time.time)
    elapsed_seconds: float = 0.0
    eta_seconds: Optional[float] = None
    
    # Recent log lines (visible in UI)
    recent_logs: List[str] = field(default_factory=list)
    max_log_lines: int = 6
    
    # Status
    status: str = "running"            # "running" | "completed" | "failed"
    error_message: Optional[str] = None


class ProgressTracker:
    """
    Thread-safe progress tracker. Attach to a pipeline run and call
    set_step(), set_substep(), heartbeat(), and log() throughout execution.
    """
    
    def __init__(self, project_id: str, task_id: str = "", store: Optional[dict] = None):
        self.state = ProgressState(project_id=project_id, task_id=task_id)
        self._lock = threading.RLock()
        self._store = store            # reference to shared progress store (dict or DB)
        self._heartbeat_thread = None
        self._heartbeat_active = False
        self._start_auto_heartbeat()
        self._update_store()

    def _append_to_file(self, message: str, level: str = "INFO"):
        """Append log message to the project's dedicated processing.log on disk."""
        try:
            from backend.core.path_utils import get_project_directory
            from datetime import datetime, timezone
            proj_dir = get_project_directory(self.state.project_id)
            proj_dir.mkdir(parents=True, exist_ok=True)
            log_file = proj_dir / "processing.log"
            iso_ts = datetime.now(timezone.utc).isoformat()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{iso_ts} - pipeline - {level} - {message}\n")
        except Exception:
            pass

    def set_step(self, step_number: int, step_name: Optional[str] = None, total_steps: Optional[int] = None):
        """Call at the beginning of each major pipeline step."""
        with self._lock:
            self.state.current_step = step_number
            self.state.step_name = step_name or STEP_LABELS.get(step_number, f"Step {step_number}")
            self.state.step_percent = 0.0
            self.state.substep = ""
            self.state.substep_current = 0
            self.state.substep_total = 0
            if total_steps is not None:
                self.state.total_steps = total_steps
            self.state.step_started_at = time.time()
            self.state.overall_percent = self._calc_overall_percent()
            self.state.elapsed_seconds = time.time() - self.state.started_at
            self._update_store()
            logger.info(f"[Progress] Step {step_number}: {self.state.step_name}")
            self._append_to_file(f"Step {step_number}: {self.state.step_name}", "INFO")

    def set_substep(self, detail: str, current: int = 0, total: int = 0):
        """
        Call during a step to show what's happening within it.
        Example: tracker.set_substep("Chunk 3 of 8 · qwen3.8-max", current=3, total=8)
        """
        with self._lock:
            self.state.substep = detail
            self.state.substep_current = current
            self.state.substep_total = total
            if total > 0:
                self.state.step_percent = round((current / total) * 100, 1)
                self.state.overall_percent = self._calc_overall_percent()
            self.state.last_heartbeat = time.time()
            self.state.elapsed_seconds = time.time() - self.state.started_at
            self._update_store()
            logger.debug(f"[Progress] Substep: {detail}")

    def heartbeat(self):
        """
        Call periodically during long operations (LLM calls, API waits).
        Keeps the UI alive indicator green.
        """
        with self._lock:
            self.state.last_heartbeat = time.time()
            self.state.elapsed_seconds = time.time() - self.state.started_at
            self._update_store()

    def log(self, message: str, level: str = "INFO"):
        """Add a line to the recent log buffer visible in the UI and write to project log."""
        with self._lock:
            timestamp = time.strftime("%H:%M:%S")
            entry = f"[{timestamp}] {message}"
            self.state.recent_logs.append(entry)
            if len(self.state.recent_logs) > self.state.max_log_lines:
                self.state.recent_logs.pop(0)
            self.state.last_heartbeat = time.time()
            self._update_store()
            logger.info(f"[Progress Log] {message}")
            self._append_to_file(message, level)

    def complete(self):
        """Call when the entire pipeline finishes successfully."""
        with self._lock:
            self.state.status = "completed"
            self.state.overall_percent = 100.0
            self.state.step_percent = 100.0
            self.state.substep = "Done"
            self.state.elapsed_seconds = time.time() - self.state.started_at
            self.state.is_alive = False
            self._stop_auto_heartbeat()
            self._update_store()
            self._append_to_file("Pipeline completed successfully. All clips rendered.", "INFO")

    def fail(self, error_message: str):
        """Call when the pipeline fails."""
        with self._lock:
            self.state.status = "failed"
            self.state.error_message = error_message
            self.state.is_alive = False
            self._stop_auto_heartbeat()
            self._update_store()
            self._append_to_file(f"Pipeline failed: {error_message}", "ERROR")

    def to_dict(self) -> dict:
        """Returns current state as a JSON-serializable dict."""
        with self._lock:
            s = self.state
            # Check if alive based on heartbeat recency and running status
            is_alive = (s.status == "running") and ((time.time() - s.last_heartbeat) < (s.heartbeat_interval * 4))
            return {
                "project_id": s.project_id,
                "task_id": s.task_id,
                "status": s.status,
                "current_step": s.current_step,
                "total_steps": s.total_steps,
                "step_name": s.step_name,
                "step_percent": round(s.step_percent, 1),
                "overall_percent": round(s.overall_percent, 1),
                "substep": s.substep,
                "substep_current": s.substep_current,
                "substep_total": s.substep_total,
                "is_alive": is_alive,
                "last_heartbeat": s.last_heartbeat,
                "elapsed_seconds": round(time.time() - s.started_at, 0),
                "eta_seconds": s.eta_seconds,
                "recent_logs": list(s.recent_logs),
                "error_message": s.error_message,
            }

    def _calc_overall_percent(self) -> float:
        s = self.state
        if s.total_steps == 0:
            return 0.0
        if s.current_step <= 0:
            within_step = (s.step_percent / 100.0) * (1.0 / s.total_steps) * 100.0 * 0.5
            return min(99.0, max(0.0, within_step))
        step_contribution = ((s.current_step - 1) / s.total_steps) * 100.0
        within_step = (s.step_percent / 100.0) * (1.0 / s.total_steps) * 100.0
        return min(99.0, max(0.0, step_contribution + within_step))

    def _update_store(self):
        """Persist current state to the shared progress store."""
        if self._store is not None:
            self._store[self.state.project_id] = self.to_dict()

    def _start_auto_heartbeat(self):
        """Background thread that pulses heartbeat every 3s automatically."""
        self._heartbeat_active = True
        def _beat():
            while self._heartbeat_active:
                time.sleep(self.state.heartbeat_interval)
                if self._heartbeat_active and self.state.status == "running":
                    self.heartbeat()
        self._heartbeat_thread = threading.Thread(target=_beat, daemon=True)
        self._heartbeat_thread.start()

    def _stop_auto_heartbeat(self):
        self._heartbeat_active = False


# ==============================================================================
# PHASE 2 — GLOBAL PROGRESS STORE
# ==============================================================================

# Global in-memory progress store
# Maps project_id -> progress dict
_progress_store: Dict[str, Any] = {}
_store_lock = threading.Lock()


def get_tracker(project_id: str, task_id: str = "") -> ProgressTracker:
    """Create and register a new tracker for a pipeline run."""
    with _store_lock:
        tracker = ProgressTracker(project_id, task_id, store=_progress_store)
        _progress_store[project_id] = tracker.to_dict()
        return tracker


def get_progress(project_id: str) -> Optional[dict]:
    """Get current progress for a project."""
    with _store_lock:
        return _progress_store.get(project_id)


def get_all_progress() -> dict:
    """Get progress for all active projects."""
    with _store_lock:
        return dict(_progress_store)


def clear_progress(project_id: str):
    """Clear progress from global store."""
    with _store_lock:
        if project_id in _progress_store:
            del _progress_store[project_id]
