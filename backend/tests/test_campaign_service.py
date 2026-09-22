import pytest
import tempfile
import subprocess
from pathlib import Path
from backend.services.campaign_service import CampaignStitchService, KETTLE_FIRE_CAMPAIGN

def test_campaign_metadata():
    """Verify campaign info contains approved sources and tagging requirements."""
    info = CampaignStitchService.get_campaign_info("kettle_fire_fasting")
    assert info["id"] == "kettle_fire_fasting"
    assert info["brand_tag"] == "@kettleandfire"
    assert len(info["approved_sources"]) >= 10
    assert any(s["id"] == "kf_founder" for s in info["approved_sources"])
    assert any(s["speaker"] == "Dana White" for s in info["approved_sources"])
    assert any(s["speaker"] == "Joe Rogan" for s in info["approved_sources"])
    assert any(s["speaker"] == "Gary Brecka" for s in info["approved_sources"])

def test_campaign_stitching_end_to_end():
    """Test stitching two synthetic video clips with combined ASS subtitle tracks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        vid_a = td / "part_a.mp4"
        vid_b = td / "part_b.mp4"
        srt_a = td / "part_a.srt"
        srt_b = td / "part_b.srt"
        out_vid = td / "stitched_campaign.mp4"

        # Generate 2-second synthetic video A
        cmd_a = [
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=2:size=1280x720:rate=30',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2',
            '-c:v', 'libx264', '-c:a', 'aac', str(vid_a)
        ]
        subprocess.run(cmd_a, capture_output=True, check=True)

        # Generate 2-second synthetic video B
        cmd_b = [
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=2:size=1280x720:rate=30',
            '-f', 'lavfi', '-i', 'sine=frequency=880:duration=2',
            '-c:v', 'libx264', '-c:a', 'aac', str(vid_b)
        ]
        subprocess.run(cmd_b, capture_output=True, check=True)

        srt_a.write_text("1\n00:00:00,000 --> 00:00:01,800\nDana White explains fasting\n", encoding="utf-8")
        srt_b.write_text("1\n00:00:00,000 --> 00:00:01,800\nKettle and Fire bone broth\n", encoding="utf-8")

        success = CampaignStitchService.stitch_campaign_clip(
            part_a_video=vid_a,
            part_b_video=vid_b,
            output_path=out_vid,
            part_a_srt=srt_a,
            part_b_srt=srt_b,
            hook_title="How The Pros Break A Fast",
            caption_style="hormozi_yellow"
        )

        assert success
        assert out_vid.exists()
        
        # Verify output duration is ~4s
        dur = CampaignStitchService.get_video_duration(out_vid)
        assert 3.8 <= dur <= 4.2
