"""
Tests for Affiliate Marketing Video Pipeline:
- Filipino/Tagalog transcription & word formatting
- Viral ASS caption generation
- FFmpeg subtitle burning
- Facebook Follow CTA overlay integration
"""

import os
import subprocess
import pytest
from pathlib import Path
from backend.affiliate.affiliate_processor import AffiliateVideoProcessor


@pytest.fixture
def sample_video(tmp_path):
    """Create a 2-second vertical test MP4 video (1080x1920) with silent audio."""
    vid_path = tmp_path / "test_affiliate_sample.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=navy:s=1080x1920:d=2",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(vid_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return vid_path


def test_affiliate_processor_init():
    proc = AffiliateVideoProcessor(whisper_model="tiny", default_caption_style="hormozi_yellow")
    assert proc.whisper_model_name == "tiny"
    assert proc.default_caption_style == "hormozi_yellow"


def test_get_video_info(sample_video):
    info = AffiliateVideoProcessor.get_video_info(sample_video)
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert info["duration"] >= 1.9


def test_export_srt(tmp_path):
    proc = AffiliateVideoProcessor()
    segments = [
        {
            "start": 0.0,
            "end": 1.5,
            "text": "Magandang araw sa inyong lahat!",
            "words": [
                {"word": "Magandang", "start": 0.0, "end": 0.5},
                {"word": "araw", "start": 0.5, "end": 0.8},
                {"word": "sa", "start": 0.8, "end": 1.0},
                {"word": "inyong", "start": 1.0, "end": 1.2},
                {"word": "lahat!", "start": 1.2, "end": 1.5}
            ]
        }
    ]
    srt_file = tmp_path / "test.srt"
    proc.export_srt(segments, srt_file)
    assert srt_file.exists()
    content = srt_file.read_text(encoding="utf-8")
    assert "Magandang araw sa inyong lahat!" in content
    assert "00:00:00,000 --> 00:00:01,500" in content


def test_generate_styled_ass(tmp_path):
    proc = AffiliateVideoProcessor(default_caption_style="hormozi_yellow")
    segments = [
        {
            "start": 0.0,
            "end": 1.8,
            "text": "Sulit itong sapatos na 'to!",
            "words": [
                {"word": "Sulit", "start": 0.0, "end": 0.4},
                {"word": "itong", "start": 0.4, "end": 0.8},
                {"word": "sapatos", "start": 0.8, "end": 1.3},
                {"word": "na", "start": 1.3, "end": 1.5},
                {"word": "'to!", "start": 1.5, "end": 1.8}
            ]
        }
    ]
    ass_file = tmp_path / "test.ass"
    proc.generate_styled_ass(
        segments=segments,
        output_ass_path=ass_file,
        video_width=1080,
        video_height=1920,
        style="hormozi_yellow"
    )
    assert ass_file.exists()
    content = ass_file.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "Style: Default" in content
    assert "SULIT" in content or "Sulit" in content


def test_burn_captions(tmp_path, sample_video):
    ass_file = tmp_path / "test_burn.ass"
    ass_file.write_text("""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,{\\b1}I-click ang link sa bio!{\\b0}
""", encoding="utf-8")

    out_video = tmp_path / "burned_video.mp4"
    res = AffiliateVideoProcessor.burn_captions(sample_video, ass_file, out_video)
    assert res.exists()
    assert res.stat().st_size > 1024


def test_apply_facebook_cta(tmp_path, sample_video):
    out_video = tmp_path / "cta_video.mp4"
    res = AffiliateVideoProcessor.apply_facebook_cta(
        input_video_path=sample_video,
        output_video_path=out_video,
        fb_handle="ShopPH",
        cta_style="pill",
        video_width=1080,
        video_height=1920,
        video_duration=2.0
    )
    assert res.exists()
    assert res.stat().st_size > 1024


def test_process_affiliate_video_end_to_end(tmp_path, sample_video, monkeypatch):
    proc = AffiliateVideoProcessor()

    # Mock transcribe_filipino to avoid downloading heavy whisper models during unit test
    def mock_transcribe(video_path, language="tl", engine="auto", **kwargs):
        return {
            "segments": [
                {
                    "start": 0.0,
                    "end": 1.5,
                    "text": "Subukan ang bagong produkto!",
                    "words": [
                        {"word": "Subukan", "start": 0.0, "end": 0.5},
                        {"word": "ang", "start": 0.5, "end": 0.7},
                        {"word": "bagong", "start": 0.7, "end": 1.1},
                        {"word": "produkto!", "start": 1.1, "end": 1.5}
                    ]
                }
            ],
            "model": "gemini-2.5-flash",
            "engine": "gemini"
        }

    monkeypatch.setattr(proc, "transcribe_filipino", mock_transcribe)

    final_output = tmp_path / "final_affiliate.mp4"
    result = proc.process_affiliate_video(
        input_video_path=sample_video,
        output_video_path=final_output,
        fb_handle="MyAffiliatePage",
        caption_style="hormozi_yellow",
        language="tl"
    )

    assert result["success"] is True
    assert Path(result["output_video"]).exists()
    assert Path(result["output_video"]).stat().st_size > 1024
    assert result["segment_count"] == 1
    assert result["word_count"] == 4
    assert result["cta_platform"] == "facebook"
    assert result["cta_handle"] == "MyAffiliatePage"


def test_parse_transcript_content_srt():
    srt_content = """1
00:00:00,000 --> 00:00:01,500
Ito ang pinakamagandang portable gas stove!

2
00:00:01,600 --> 00:00:03,200
Subukan na natin agad.
"""
    segments = AffiliateVideoProcessor.parse_transcript_content(srt_content)
    assert segments is not None
    assert len(segments) == 2
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 1.5
    assert segments[0]["text"] == "Ito ang pinakamagandang portable gas stove!"
    assert len(segments[0]["words"]) == 6
    assert segments[0]["words"][0]["word"] == "Ito"
    assert segments[1]["start"] == 1.6
    assert segments[1]["end"] == 3.2


def test_parse_transcript_content_vtt():
    vtt_content = """WEBVTT

00:00:00.500 --> 00:00:02.000
Sobrang comfy nitong sneakers na 'to!
"""
    segments = AffiliateVideoProcessor.parse_transcript_content(vtt_content)
    assert segments is not None
    assert len(segments) == 1
    assert segments[0]["start"] == 0.5
    assert segments[0]["end"] == 2.0
    assert len(segments[0]["words"]) == 6


def test_process_affiliate_video_with_custom_transcript_file(tmp_path, sample_video):
    proc = AffiliateVideoProcessor()
    
    # Create custom user SRT file
    custom_srt = tmp_path / "custom_input.srt"
    custom_srt.write_text("""1
00:00:00,000 --> 00:00:01,200
Custom Affiliate Review

2
00:00:01,300 --> 00:00:02,000
Solid and Sulit!
""", encoding="utf-8")

    out_video = tmp_path / "custom_affiliate_output.mp4"
    result = proc.process_affiliate_video(
        input_video_path=sample_video,
        output_video_path=out_video,
        transcript_source=custom_srt,
        fb_handle="ShopPH",
        caption_style="hormozi_yellow"
    )

    assert result["success"] is True
    assert result["transcript_provided"] is True
    assert result["segment_count"] == 2
    assert result["model_used"] == "user-transcript-file"
    assert Path(result["output_video"]).exists()
    assert Path(result["output_video"]).stat().st_size > 1024
