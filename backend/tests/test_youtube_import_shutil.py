"""Test YouTube import and helper functions."""
from unittest.mock import patch, MagicMock
from backend.api.v1.youtube import _find_node_bin, robust_extract_youtube_info


def test_find_node_bin_does_not_raise():
    """Verify _find_node_bin runs cleanly without NameError."""
    node_bin = _find_node_bin()
    # It either returns None or a valid string path
    assert node_bin is None or isinstance(node_bin, str)


def test_robust_extract_youtube_info_mocked():
    """Verify robust_extract_youtube_info executes without module import errors."""
    fake_info = {
        "title": "Test Title",
        "description": "Test Desc",
        "duration": 120,
        "uploader": "Tester",
        "upload_date": "20260101",
        "view_count": 1000,
        "like_count": 50,
        "thumbnail": "https://example.com/thumb.jpg"
    }
    with patch("subprocess.run") as mock_run:
        import json
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(fake_info),
            stderr=""
        )
        res = robust_extract_youtube_info("https://youtube.com/watch?v=12345")
        assert res["title"] == "Test Title"
        assert res["duration"] == 120
