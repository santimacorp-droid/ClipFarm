"""
End-to-End Pipeline Smoke Test
Validates that the entire video processing pipeline executes end-to-end without Redis,
producing vertical clips and updating SQLite database state.
"""
import os
import time
import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.core.database import SessionLocal, get_db
from backend.models.project import Project, ProjectStatus
from backend.models.clip import Clip
from backend.models.task import Task, TaskStatus
from backend.services.project_service import ProjectService
from backend.utils.task_submission_utils import submit_video_pipeline_task
from backend.core.path_utils import get_project_directory


def _generate_synthetic_video(output_path: Path, duration: int = 2) -> None:
    """Generate a quick synthetic 1080x1920 video with test audio tone."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=navy:s=1080x1920:d={duration}:r=24",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic video generation failed: {res.stderr}")


def _generate_synthetic_srt(output_path: Path) -> None:
    """Generate sample SRT subtitle file."""
    srt_content = """1
00:00:00,000 --> 00:00:01,000
Welcome to ClipFarm AI Studio.

2
00:00:01,000 --> 00:00:02,000
This is a high impact viral clip test.
"""
    output_path.write_text(srt_content, encoding="utf-8")


def test_end_to_end_local_pipeline_execution(tmp_path):
    """
    End-to-end test running the full video pipeline in zero-Redis local mode.
    Verifies that:
    1. Task is accepted and dispatched to local background thread
    2. Video processing stages execute cleanly
    3. Output clips are generated on disk
    4. SQLite database reflects COMPLETED project status and created clips
    """
    import uuid
    project_id = f"smoke-{uuid.uuid4().hex[:8]}"

    # Setup directories
    proj_dir = get_project_directory(project_id)
    metadata_dir = proj_dir / "metadata"
    output_dir = proj_dir / "output"
    clips_dir = output_dir / "clips"
    collections_dir = output_dir / "collections"

    metadata_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)
    collections_dir.mkdir(parents=True, exist_ok=True)

    input_video = proj_dir / "input.mp4"
    input_srt = metadata_dir / "input.srt"

    _generate_synthetic_video(input_video, duration=2)
    _generate_synthetic_srt(input_srt)

    # Pre-seed step1 outline so we don't depend on external LLM rate limits/keys during CI
    outline_data = [
        {
            "title": "Viral Hook Moment",
            "subtopics": ["Welcome to ClipFarm AI Studio"],
            "chunk_index": 0,
            "category": "general",
            "start_time": "00:00:00",
            "end_time": "00:00:02",
            "source_model": "test",
            "confidence": "high"
        }
    ]
    with open(metadata_dir / "step1_outline.json", "w", encoding="utf-8") as f:
        json.dump(outline_data, f, indent=2)

    # Create project in DB
    with SessionLocal() as db:
        project = Project(
            id=project_id,
            name="Smoke Test Project",
            status=ProjectStatus.PROCESSING,
            video_path=str(input_video),
            subtitle_path=str(input_srt),
            processing_config={
                "aspect_ratio": "9:16_blur",
                "caption_style": "hormozi_yellow",
                "show_hook_banner": False
            }
        )
        db.add(project)
        db.commit()

    # Mock LLM calls so the smoke test executes fast & offline without network flakiness
    def _mock_llm_call(prompt, input_data=None, **kwargs):
        task = kwargs.get("task", "")
        prompt_str = str(prompt).lower()

        # If titling
        if "titling" in task or "title" in prompt_str:
            input_list = input_data if isinstance(input_data, list) else [{}]
            res = {}
            for idx, clip in enumerate(input_list):
                cid = str(clip.get("id", idx + 1))
                res[cid] = {
                    "title": "ClipFarm AI Viral Hook",
                    "hook_title": "Watch This",
                    "hook_text": "ClipFarm AI Studio",
                    "category": "general"
                }
            return json.dumps(res)

        # If scoring
        elif "scoring" in task or "recommend" in prompt_str or "score" in prompt_str:
            input_list = input_data if isinstance(input_data, list) else [{}]
            return json.dumps([
                {
                    "id": clip.get("id", idx + 1),
                    "score": 0.95,
                    "recommend_reason": "High hook score",
                    "what_makes_this_distinctive": "Engaging hook delivery",
                    "creativity_score": 0.9
                }
                for idx, clip in enumerate(input_list)
            ])

        # If clustering
        elif "cluster" in task or "collection" in prompt_str:
            return json.dumps([
                {
                    "collection_title": "ClipFarm Highlights",
                    "collection_summary": "Top viral clips",
                    "clips": ["ClipFarm AI Viral Hook", "Viral Hook Moment"]
                }
            ])

        return json.dumps([
            {
                "title": "Viral Hook Moment",
                "subtopics": ["Welcome to ClipFarm AI Studio"],
                "start_time": "00:00:00",
                "end_time": "00:00:02"
            }
        ])

    with patch("backend.utils.llm_client.LLMClient.call_with_retry", side_effect=_mock_llm_call), \
         patch("backend.utils.llm_client.LLMClient.call", side_effect=_mock_llm_call):

        # Submit task via zero-Redis dispatcher
        result = submit_video_pipeline_task(project_id, str(input_video), str(input_srt))
        assert result["success"] is True
        assert "task_id" in result

        # Poll for completion (max 20 seconds, typical execution is ~2s)
        max_wait = 20
        start_time = time.time()
        completed = False

        while time.time() - start_time < max_wait:
            with SessionLocal() as db:
                p = db.query(Project).filter(Project.id == project_id).first()
                if p and p.status in [ProjectStatus.COMPLETED, ProjectStatus.FAILED]:
                    completed = True
                    assert p.status == ProjectStatus.COMPLETED, f"Pipeline failed with error"
                    break
            time.sleep(0.5)

    assert completed is True, f"Pipeline timed out after {max_wait}s"

    # Verify output clips exist
    with SessionLocal() as db:
        clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        assert len(clips) > 0, "At least one clip should be recorded in database"
        for clip in clips:
            clip_path = Path(clip.video_path)
            assert clip_path.exists(), f"Clip file must exist: {clip_path}"
            assert clip_path.stat().st_size > 1000, f"Clip file too small: {clip_path}"

        # Verify task is completed
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        assert any(t.status == TaskStatus.COMPLETED for t in tasks)
