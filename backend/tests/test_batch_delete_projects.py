"""Tests for batch delete projects endpoint."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import app

client = TestClient(app)


def test_batch_delete_projects():
    """Test batch deleting projects with mocked project service."""
    with patch("backend.api.v1.projects.ProjectService") as MockService:
        mock_instance = MockService.return_value
        # Suppose id-1 and id-2 succeed, id-3 fails
        mock_instance.delete_project_with_files.side_effect = lambda pid: pid in ["id-1", "id-2"]

        response = client.post(
            "/api/v1/projects/batch-delete",
            json={"project_ids": ["id-1", "id-2", "id-3"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["deleted"] == ["id-1", "id-2"]
        assert data["failed"] == ["id-3"]
        assert "Successfully deleted 2 projects" in data["message"]


def test_batch_delete_empty_list():
    """Test batch delete with empty list of project ids."""
    response = client.post(
        "/api/v1/projects/batch-delete",
        json={"project_ids": []}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["deleted"] == []
    assert data["failed"] == []
