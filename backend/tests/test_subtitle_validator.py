import pytest
from pathlib import Path
from backend.utils.subtitle_validator import validate_subtitle_file


def test_reject_none_or_missing_file(tmp_path):
    assert validate_subtitle_file(None) is False
    assert validate_subtitle_file(tmp_path / "non_existent.srt") is False


def test_reject_dummy_5s_placeholder(tmp_path):
    placeholder = tmp_path / "input.srt"
    placeholder.write_text("1\n00:00:00,000 --> 00:00:05,000\n\n", encoding="utf-8")
    assert validate_subtitle_file(placeholder) is False


def test_reject_explicit_placeholder_sentinel(tmp_path):
    dummy = tmp_path / "dummy.srt"
    dummy.write_text("1\n00:00:00,000 --> 00:01:00,000\n# PLACEHOLDER SUBTITLE\n\n", encoding="utf-8")
    assert validate_subtitle_file(dummy) is False


def test_reject_empty_cues_or_whitespace(tmp_path):
    blank = tmp_path / "blank.srt"
    blank.write_text("1\n00:00:00,000 --> 00:00:10,000\n   \n\n2\n00:00:10,000 --> 00:00:20,000\n\n", encoding="utf-8")
    assert validate_subtitle_file(blank) is False


def test_reject_duration_mismatch_with_video(tmp_path, monkeypatch):
    short_srt = tmp_path / "short.srt"
    short_srt.write_text(
        "1\n00:00:00,000 --> 00:00:04,000\nHello world\n\n"
        "2\n00:00:04,000 --> 00:00:08,000\nQuick test\n\n",
        encoding="utf-8"
    )

    fake_video = tmp_path / "input.mp4"
    fake_video.write_bytes(b"0" * 1024)

    # Mock video duration to 800 seconds (13 minutes)
    monkeypatch.setattr(
        "backend.utils.subtitle_validator.get_video_duration_seconds",
        lambda p: 800.0
    )

    # An 8-second SRT on an 800-second video must be rejected!
    assert validate_subtitle_file(short_srt, video_path=fake_video) is False


def test_accept_valid_subtitles(tmp_path, monkeypatch):
    valid_srt = tmp_path / "valid.srt"
    valid_srt.write_text(
        "1\n00:00:00,000 --> 00:01:30,000\nFirst substantial conversation about leadership.\n\n"
        "2\n00:01:30,000 --> 00:04:00,000\nSecond key narrative explaining the inflection point.\n\n",
        encoding="utf-8"
    )

    fake_video = tmp_path / "input.mp4"
    fake_video.write_bytes(b"0" * 1024)

    monkeypatch.setattr(
        "backend.utils.subtitle_validator.get_video_duration_seconds",
        lambda p: 260.0
    )

    assert validate_subtitle_file(valid_srt, video_path=fake_video) is True
