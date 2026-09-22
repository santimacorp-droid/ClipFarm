"""Tests for campaign caption burning, subtitle mode extraction, and ASS filter execution."""
import pytest
import subprocess
from pathlib import Path
from backend.campaign.campaign_pipeline import (
    _get_subtitle_mode,
    _get_caption_style,
    _burn_ass_captions
)
from backend.schemas.campaign import (
    CampaignSchema,
    CampaignRestrictions,
    SubtitleMode,
    CampaignCaptionStyle
)


def test_get_subtitle_mode():
    # 1. Pydantic model with SubtitleMode Enum
    schema1 = CampaignSchema(
        brand_name="Test",
        restrictions=CampaignRestrictions(subtitles=SubtitleMode.styled_burned)
    )
    assert _get_subtitle_mode(schema1) == "styled_burned"

    # 2. Raw dict
    schema2 = {
        "restrictions": {
            "subtitles": "clean_srt_only"
        }
    }
    assert _get_subtitle_mode(schema2) == "clean_srt_only"

    # 3. Default fallback
    schema3 = {}
    assert _get_subtitle_mode(schema3) == "native_preferred"


def test_get_caption_style():
    # 1. Pydantic model with CampaignCaptionStyle Enum
    schema1 = CampaignSchema(
        brand_name="Test",
        restrictions=CampaignRestrictions(caption_style=CampaignCaptionStyle.neon_green)
    )
    assert _get_caption_style(schema1) == "neon_green"

    # 2. Raw dict
    schema2 = {
        "restrictions": {
            "caption_style": "minimal_box"
        }
    }
    assert _get_caption_style(schema2) == "minimal_box"

    # 3. Default fallback
    schema3 = {}
    assert _get_caption_style(schema3) == "hormozi_yellow"


def test_burn_ass_captions_success(tmp_path):
    # Create 1s black video
    video_input = tmp_path / "test_input.mp4"
    cmd_in = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_input)
    ]
    subprocess.run(cmd_in, capture_output=True, check=True)

    # Create dummy ASS file
    ass_file = tmp_path / "captions.ass"
    ass_file.write_text("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,{\\b1}Test Caption{\\b0}
""", encoding="utf-8")

    video_output = tmp_path / "test_captioned.mp4"

    ok = _burn_ass_captions(video_input, ass_file, video_output)
    assert ok is True
    assert video_output.exists()
    assert video_output.stat().st_size > 1000


def test_pipeline_caption_burning_integration(tmp_path, monkeypatch):
    from backend.campaign.campaign_pipeline import run_campaign_pipeline
    import backend.campaign.campaign_pipeline as cp_module
    from backend.core.database import SessionLocal
    from backend.models.campaign import Campaign, CampaignClip
    import json

    monkeypatch.setattr(cp_module, "CAMPAIGN_DATA_DIR", tmp_path)

    import uuid
    campaign_id = f"test-camp-captions-{uuid.uuid4().hex[:8]}"
    camp_dir = tmp_path / campaign_id
    camp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate 3-second source video
    source_vid = camp_dir / "source.mp4"
    cmd_vid = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=3",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source_vid)
    ]
    subprocess.run(cmd_vid, capture_output=True, check=True)

    # 2. Write transcript.srt
    srt_file = camp_dir / "transcript.srt"
    srt_file.write_text(
        "1\n00:00:00,500 --> 00:00:02,500\nHello and welcome to the test campaign\n",
        encoding="utf-8"
    )

    # 3. Create campaign in DB
    db = SessionLocal()
    try:
        camp = Campaign(
            id=campaign_id,
            name="Test Captions Campaign",
            brand_name="TestBrand",
            status="draft",
            schema_json="{}"
        )
        db.add(camp)
        db.commit()
    finally:
        db.close()

    schema_dict = {
        "brand_name": "TestBrand",
        "campaign_name": "Test Captions Campaign",
        "source_video_url": None,
        "logo_url": None,
        "clip_duration": {"min_seconds": 1.0, "max_seconds": 3.0},
        "priority_moments": [{"name": "Welcome Moment", "start_line": "Hello and welcome"}],
        "restrictions": {
            "subtitles": "styled_burned",
            "caption_style": "hormozi_yellow",
            "styled_captions": True,
            "show_hook_banner": False,
            "output_format": "original",
            "logo_required": False
        },
        "compliance": {
            "min_days_live": 30,
            "min_engagement_rate": 0.002,
            "likes_must_be_visible": True,
            "tier1_2_audience_required": True,
            "ftc_compliant": True
        }
    }

    # Run pipeline
    run_campaign_pipeline(campaign_id, schema_dict)

    # Check DB
    db = SessionLocal()
    try:
        clips = db.query(CampaignClip).filter_by(campaign_id=campaign_id).all()
        assert len(clips) >= 1
        clip = clips[0]
        data = json.loads(clip.clip_data_json)
        assert data["subtitle_mode"] == "styled_burned"
        assert data["captioned_video_file"] is not None
        assert Path(data["captioned_video_file"]).exists()
        assert data["video_file"] == data["captioned_video_file"]

        # Clean up DB
        db.query(CampaignClip).filter_by(campaign_id=campaign_id).delete()
        db.query(Campaign).filter_by(id=campaign_id).delete()
        db.commit()
    finally:
        db.close()

