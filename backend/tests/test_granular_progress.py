"""
Tests for Granular Progress Tracking System
"""

import time
import pytest
from backend.core.progress_tracker import get_tracker, get_progress, get_all_progress, clear_progress, ProgressTracker


def test_progress_tracker_state_transitions():
    proj_id = "test-proj-unit"
    task_id = "task-unit-1"
    tracker = get_tracker(proj_id, task_id)
    
    # Initial state
    assert tracker.state.current_step == 0
    assert tracker.state.status == "running"
    
    # Step 1: Finding Key Moments
    tracker.set_step(1, "Finding Key Moments", total_steps=6)
    assert tracker.state.current_step == 1
    assert tracker.state.step_name == "Finding Key Moments"
    assert tracker.state.step_percent == 0.0
    assert tracker.state.overall_percent == 0.0
    
    # Substeps
    tracker.set_substep("Chunk 1 of 4 · qwen-plus", current=1, total=4)
    tracker.log("Found 3 moments in chunk 1")
    assert tracker.state.substep_current == 1
    assert tracker.state.step_percent == 25.0
    
    tracker.set_substep("Chunk 2 of 4 · deepseek-v4", current=2, total=4)
    tracker.log("Found 5 moments in chunk 2")
    assert tracker.state.substep_current == 2
    assert tracker.state.step_percent == 50.0
    assert len(tracker.state.recent_logs) == 2
    
    # Check to_dict representation
    d = tracker.to_dict()
    assert d["project_id"] == proj_id
    assert d["current_step"] == 1
    assert d["substep"] == "Chunk 2 of 4 · deepseek-v4"
    assert d["substep_current"] == 2
    assert d["substep_total"] == 4
    assert d["step_percent"] == 50.0
    assert d["is_alive"] is True
    assert len(d["recent_logs"]) == 2
    
    # Global store lookup
    stored = get_progress(proj_id)
    assert stored is not None
    assert stored["substep_current"] == 2
    
    # Complete
    tracker.complete()
    assert tracker.state.status == "completed"
    assert tracker.state.overall_percent == 100.0
    assert tracker.to_dict()["is_alive"] is False
    
    clear_progress(proj_id)
    assert get_progress(proj_id) is None


def test_progress_tracker_max_log_buffer():
    proj_id = "test-proj-buffer"
    tracker = get_tracker(proj_id)
    for i in range(10):
        tracker.log(f"Message {i}")
    
    assert len(tracker.state.recent_logs) == 6
    assert "Message 9" in tracker.state.recent_logs[-1]
    assert "Message 4" in tracker.state.recent_logs[0]
    tracker.complete()
    clear_progress(proj_id)


def test_progress_api_integration():
    from fastapi.testclient import TestClient
    from backend.app_factory import create_app
    
    proj_id = "test-proj-api"
    tracker = get_tracker(proj_id, "task-api")
    tracker.set_step(3, "Scoring Clips")
    tracker.set_substep("Clip 2 of 5 · qwen", current=2, total=5)
    tracker.log("Scored clip 2")
    
    app = create_app(mode="web")
    client = TestClient(app)
    
    res = client.get("/api/v1/progress")
    assert res.status_code == 200
    assert proj_id in res.json()["projects"]
    
    res_single = client.get(f"/api/v1/progress/{proj_id}")
    assert res_single.status_code == 200
    assert res_single.json()["current_step"] == 3
    assert res_single.json()["substep_current"] == 2
    
    tracker.complete()
    clear_progress(proj_id)
