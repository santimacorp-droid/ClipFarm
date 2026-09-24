import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from pathlib import Path

from backend.main import app
from backend.core.database import SessionLocal, Base, engine
from backend.models.project import Project, ProjectStatus, ProjectType
from backend.models.clip import Clip


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_youtube_parse_invalid_url(client):
    """Ensure non-YouTube URLs are rejected with a clear 400 error."""
    response = client.post("/api/v1/youtube/parse", data={"url": "https://example.com/video.mp4"})
    assert response.status_code == 400
    assert "invalid" in response.json().get("detail", "").lower() or "youtube" in response.json().get("detail", "").lower()


def test_project_reveal_nonexistent(client):
    """Ensure revealing a non-existent project returns 404."""
    response = client.post("/api/v1/projects/non-existent-proj-id-999/reveal")
    assert response.status_code == 404


def test_project_reveal_success(client, db_session, tmp_path, monkeypatch):
    """Ensure revealing an existing project returns 200 and invokes file manager."""
    proj = Project(
        name="Reveal Test Project",
        description="Test",
        project_type=ProjectType.DEFAULT,
        status=ProjectStatus.COMPLETED,
        video_path=str(tmp_path / "input.mp4")
    )
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    proj_id = str(proj.id)

    with patch("backend.core.path_utils.reveal_in_file_manager", return_value=True) as mock_reveal:
        response = client.post(f"/api/v1/projects/{proj_id}/reveal")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "path" in data
        mock_reveal.assert_called_once()

    # Clean up
    db_session.delete(proj)
    db_session.commit()


def test_clip_reveal_nonexistent(client):
    """Ensure revealing a non-existent clip returns 404."""
    response = client.post("/api/v1/clips/non-existent-clip-id-999/reveal")
    assert response.status_code == 404


def test_clip_reveal_success(client, db_session, tmp_path):
    """Ensure revealing an existing clip returns 200 and invokes file manager."""
    proj = Project(
        name="Clip Reveal Proj",
        description="Test",
        project_type=ProjectType.DEFAULT,
        status=ProjectStatus.COMPLETED,
        video_path=str(tmp_path / "input.mp4")
    )
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    clip = Clip(
        project_id=proj.id,
        title="Sample Highlight Clip",
        start_time=5,
        end_time=20,
        duration=15,
        score=9.5,
        description="Test outline"
    )
    db_session.add(clip)
    db_session.commit()
    db_session.refresh(clip)

    clip_id = str(clip.id)

    with patch("backend.core.path_utils.reveal_in_file_manager", return_value=True) as mock_reveal:
        response = client.post(f"/api/v1/clips/{clip_id}/reveal")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        mock_reveal.assert_called_once()

    # Clean up
    db_session.delete(clip)
    db_session.delete(proj)
    db_session.commit()


def test_project_status_reporting_download_progress(client, db_session):
    """Ensure project status accurately reports ongoing yt-dlp download progress."""
    proj = Project(
        name="Download Status Test",
        description="Test",
        project_type=ProjectType.DEFAULT,
        status=ProjectStatus.PENDING,
        processing_config={
            "download_status": "downloading",
            "download_progress": 42.5,
            "download_message": "Downloading: 42.5MB / 100MB"
        }
    )
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)

    proj_id = str(proj.id)

    response = client.get(f"/api/v1/projects/{proj_id}/status")
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["status"] == "processing"
    assert status_data["progress"] == 42.5
    assert "Downloading" in status_data["step_name"]

    # Clean up
    db_session.delete(proj)
    db_session.commit()
