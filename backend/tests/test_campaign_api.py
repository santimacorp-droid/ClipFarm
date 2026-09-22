"""Tests for Campaign API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import app

client = TestClient(app)

SAMPLE_BRIEF = """
Brand: Frida
Frida - Dr. Rosen Episode 1 Clipping
Clip moments between 15-40s.
Moments to prioritize:
- The ant and the cookie
TAGGING REQUIREMENT: TikTok: tag @frida
"""

def test_campaign_crud_endpoints():
    mock_parsed = {
        "brand_name": "Frida",
        "campaign_name": "Frida - Dr. Rosen Episode 1 Clipping",
        "source_video_url": None,
        "logo_url": None,
        "clip_duration": {"min_seconds": 15, "max_seconds": 40},
        "priority_moments": [{"name": "The ant and the cookie", "start_line": "Ants"}],
        "caption_options": ["Great caption"],
        "platform_tags": {"tiktok": ["@frida"], "instagram": [], "youtube_shorts": []},
        "restrictions": {
            "subtitles": "native_preferred",
            "styled_captions": False,
            "background_music": "allowed_low",
            "logo_required": True,
            "logo_position": "top_right",
            "logo_scale_percent": 0.12,
            "other_people_allowed": False,
            "external_footage_allowed": False,
            "filters_allowed": False
        },
        "compliance": {
            "min_days_live": 30,
            "min_engagement_rate": 0.002,
            "likes_must_be_visible": True,
            "tier1_2_audience_required": True,
            "ftc_compliant": True
        }
    }

    with patch("backend.api.v1.campaigns.parse_brief", return_value=mock_parsed):
        # 1. Create
        create_res = client.post("/api/v1/campaigns", json={"raw_brief": SAMPLE_BRIEF})
        assert create_res.status_code == 200, create_res.text
        data = create_res.json()
        campaign_id = data["id"]
        assert data["name"] == "Frida - Dr. Rosen Episode 1 Clipping"
        assert data["brand_name"] == "Frida"
        assert data["status"] == "draft"

        # 2. List
        list_res = client.get("/api/v1/campaigns")
        assert list_res.status_code == 200
        camp_list = list_res.json()
        assert any(c["id"] == campaign_id for c in camp_list)

        # 3. Get
        get_res = client.get(f"/api/v1/campaigns/{campaign_id}")
        assert get_res.status_code == 200
        detail = get_res.json()
        assert detail["id"] == campaign_id
        assert detail["schema"]["brand_name"] == "Frida"

        # 4. Update
        updated_schema = dict(mock_parsed)
        updated_schema["campaign_name"] = "Frida - Updated Name"
        put_res = client.put(f"/api/v1/campaigns/{campaign_id}", json={"schema_json": updated_schema})
        assert put_res.status_code == 200

        # Verify update
        get_updated = client.get(f"/api/v1/campaigns/{campaign_id}").json()
        assert get_updated["name"] == "Frida - Updated Name"

        # 5. Delete
        del_res = client.delete(f"/api/v1/campaigns/{campaign_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify deleted
        assert client.get(f"/api/v1/campaigns/{campaign_id}").status_code == 404


def test_campaign_video_and_assets():
    """Test parse-brief, video upload, source info, logo upload, and run validation."""
    # 1. Fast parse brief
    parse_res = client.post("/api/v1/campaigns/parse-brief", json={
        "raw_brief": SAMPLE_BRIEF,
        "use_llm": False
    })
    assert parse_res.status_code == 200
    parsed = parse_res.json()
    assert parsed["brand_name"] == "Frida"

    # 2. Instant create
    create_res = client.post("/api/v1/campaigns", json={"schema_json": parsed})
    assert create_res.status_code == 200
    camp_id = create_res.json()["id"]

    try:
        # 3. Check source info before video (should not exist)
        info_res = client.get(f"/api/v1/campaigns/{camp_id}/source-info")
        assert info_res.status_code == 200
        assert info_res.json().get("exists") is False

        # 4. Try run without video (should return 400)
        run_res = client.post(f"/api/v1/campaigns/{camp_id}/run")
        assert run_res.status_code == 400
        assert "Source video missing" in run_res.json()["detail"]

        # 5. Upload mock video
        fake_video = b"\x00\x00\x00\x20ftypisom" + b"A" * 2000
        upload_res = client.post(
            f"/api/v1/campaigns/{camp_id}/upload-video",
            files={"video_file": ("test_vid.mp4", fake_video, "video/mp4")}
        )
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        assert upload_data["status"] == "uploaded"
        assert upload_data["filename"] == "test_vid.mp4"

        # 6. Check source info after video
        info_after = client.get(f"/api/v1/campaigns/{camp_id}/source-info").json()
        assert info_after["exists"] is True

        # 7. Upload mock logo
        fake_logo = b"\x89PNG\r\n\x1a\n" + b"B" * 500
        logo_res = client.post(
            f"/api/v1/campaigns/{camp_id}/upload-logo",
            files={"logo_file": ("brand_logo.png", fake_logo, "image/png")}
        )
        assert logo_res.status_code == 200
        assert logo_res.json()["status"] == "uploaded"

        # 8. Test HEAD and GET on source-video and logo
        source_head = client.head(f"/api/v1/campaigns/{camp_id}/source-video")
        assert source_head.status_code == 200
        assert "video/mp4" in source_head.headers.get("content-type", "")
        assert source_head.headers.get("accept-ranges") == "bytes"

        logo_head = client.head(f"/api/v1/campaigns/{camp_id}/logo")
        assert logo_head.status_code == 200
        assert "image/png" in logo_head.headers.get("content-type", "")

        # 9. Test clip video HEAD and GET with mock clip in DB
        from backend.core.database import SessionLocal
        from backend.models.campaign import CampaignClip
        import json as _json

        db = SessionLocal()
        try:
            mock_clip = CampaignClip(
                campaign_id=camp_id,
                moment_name="Test Moment",
                clip_data_json=_json.dumps({
                    "id": "clip-1234",
                    "campaign_id": camp_id,
                    "moment_name": "Test Moment",
                    "video_file": f"data/campaigns/{camp_id}/source.mp4"
                })
            )
            db.add(mock_clip)
            db.commit()
            db.refresh(mock_clip)
            clip_id = mock_clip.id
        finally:
            db.close()

        clip_head = client.head(f"/api/v1/campaigns/{camp_id}/clips/{clip_id}/video")
        assert clip_head.status_code == 200
        assert "video/mp4" in clip_head.headers.get("content-type", "")
        assert clip_head.headers.get("accept-ranges") == "bytes"
        assert "inline" in clip_head.headers.get("content-disposition", "")

        clip_get = client.get(f"/api/v1/campaigns/{camp_id}/clips/{clip_id}/video")
        assert clip_get.status_code == 200
        assert "video/mp4" in clip_get.headers.get("content-type", "")

        # 10. Test reset endpoint
        reset_res = client.post(f"/api/v1/campaigns/{camp_id}/reset")
        assert reset_res.status_code == 200
        assert reset_res.json()["status"] == "reset"

        # Verify status is draft
        camp_check = client.get(f"/api/v1/campaigns/{camp_id}").json()
        assert camp_check["status"] == "draft"

        # 11. Test SRT endpoint with nonexistent clip / nonexistent srt
        fake_clip_id = "00000000-0000-0000-0000-000000000000"
        srt_404 = client.get(f"/api/v1/campaigns/{camp_id}/clips/{fake_clip_id}/srt")
        assert srt_404.status_code == 404

    finally:
        # Clean up
        client.delete(f"/api/v1/campaigns/{camp_id}")


