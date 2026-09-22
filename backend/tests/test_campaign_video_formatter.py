"""Tests for campaign video formatter (9:16 vertical conversion)."""
import pytest
from pathlib import Path
from backend.campaign.video_formatter import (
    is_vertical,
    _build_crop_center_filter,
    _build_blur_pad_filter,
    format_to_vertical
)

def test_is_vertical():
    assert is_vertical(1080, 1920) is True
    assert is_vertical(720, 1280) is True
    assert is_vertical(1920, 1080) is False
    assert is_vertical(1080, 1080) is False

def test_build_crop_center_filter():
    vf = _build_crop_center_filter()
    assert "crop=ih*9/16:ih" in vf
    assert "scale=1080:1920" in vf

def test_build_blur_pad_filter():
    vf = _build_blur_pad_filter()
    assert "split[fg][bg]" in vf
    assert "gblur=sigma=25" in vf
    assert "overlay=(W-w)/2:(H-h)/2" in vf

def test_format_to_vertical_original_bypass(tmp_path):
    # If mode is original, should copy without running ffmpeg
    dummy_input = tmp_path / "dummy_input.mp4"
    dummy_input.write_bytes(b"dummy video data")
    dummy_output = tmp_path / "dummy_output.mp4"

    res = format_to_vertical(dummy_input, dummy_output, mode="original")
    assert res is True
    assert dummy_output.exists()
    assert dummy_output.read_bytes() == b"dummy video data"
