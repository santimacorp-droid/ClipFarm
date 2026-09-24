import pytest
from pathlib import Path
from unittest.mock import MagicMock
from backend.core.progress_tracker import get_tracker, get_progress, clear_progress
from backend.models.project import Project, ProjectStatus
from backend.models.task import Task, TaskStatus


def test_progress_tracker_lifecycle_and_file_logging(tmp_path: Path, monkeypatch):
    """Verify ProgressTracker tracks steps, updates store, and writes to project log."""
    project_id = "test_proj_123"
    clear_progress(project_id)

    # Mock get_project_directory to point to tmp_path
    monkeypatch.setattr("backend.core.path_utils.get_project_directory", lambda pid: tmp_path / pid)

    tracker = get_tracker(project_id, task_id="task_abc")
    tracker.set_step(1, "Finding Key Moments", total_steps=6)
    tracker.set_substep("Chunk 1 of 3 · testing", current=1, total=3)
    tracker.log("First candidate moment detected at 00:01:23")

    # Verify in-memory state
    state = get_progress(project_id)
    assert state is not None
    assert state["current_step"] == 1
    assert state["step_name"] == "Finding Key Moments"
    assert state["substep"] == "Chunk 1 of 3 · testing"
    assert state["overall_percent"] > 0
    assert any("First candidate moment detected" in l for l in state["recent_logs"])

    # Verify disk log file
    log_file = tmp_path / project_id / "processing.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Step 1: Finding Key Moments" in content
    assert "First candidate moment detected at 00:01:23" in content

    # Complete pipeline
    tracker.complete()
    completed_state = get_progress(project_id)
    assert completed_state["status"] == "completed"
    assert completed_state["overall_percent"] == 100.0

    clear_progress(project_id)


def test_progress_tracker_fail(tmp_path: Path, monkeypatch):
    """Verify ProgressTracker fail handles errors and writes to disk."""
    project_id = "test_fail_proj"
    clear_progress(project_id)
    monkeypatch.setattr("backend.core.path_utils.get_project_directory", lambda pid: tmp_path / pid)

    tracker = get_tracker(project_id)
    tracker.fail("FFmpeg encoder out of memory error")

    state = get_progress(project_id)
    assert state["status"] == "failed"
    assert state["error_message"] == "FFmpeg encoder out of memory error"

    log_file = tmp_path / project_id / "processing.log"
    assert log_file.exists()
    assert "Pipeline failed: FFmpeg encoder out of memory error" in log_file.read_text(encoding="utf-8")

    clear_progress(project_id)


@pytest.mark.asyncio
async def test_get_processing_status_completed(tmp_path: Path):
    """Test get_processing_status for a completed project."""
    from backend.api.v1.projects import get_processing_status
    mock_ps = MagicMock()
    mock_proc_s = MagicMock()

    mock_project = MagicMock()
    mock_project.status = ProjectStatus.COMPLETED
    mock_project.tasks = []
    mock_ps.get.return_value = mock_project

    res = await get_processing_status("proj_done", project_service=mock_ps, processing_service=mock_proc_s)
    assert res["status"] == "completed"
    assert res["progress"] == 100.0
    assert res["current_step"] == 6


@pytest.mark.asyncio
async def test_get_project_logs_from_file(tmp_path: Path, monkeypatch):
    """Test get_project_logs reads actual lines from disk."""
    from backend.api.v1.projects import get_project_logs
    mock_ps = MagicMock()
    project_id = "proj_log_test"

    proj_dir = tmp_path / project_id
    proj_dir.mkdir(parents=True)
    log_file = proj_dir / "processing.log"
    log_file.write_text("2026-09-24T12:00:00Z - pipeline - INFO - Initialized pipeline\n2026-09-24T12:01:00Z - pipeline - INFO - Cut 3 clips\n")

    monkeypatch.setattr("backend.core.path_utils.get_project_directory", lambda pid: tmp_path / pid)

    res = await get_project_logs(project_id, lines=50, project_service=mock_ps)
    assert "logs" in res
    assert len(res["logs"]) == 2
    assert res["logs"][0]["message"] == "Initialized pipeline"
    assert res["logs"][1]["message"] == "Cut 3 clips"

