"""
Unit and integration tests for hardware acceleration, progress reporting, and error handling.
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from backend.utils.video_processor import (
    detect_hw_accel,
    build_ffmpeg_cut_command,
    VideoProcessor,
    ACTIVE_HW_ACCEL,
)
from backend.core.progress_tracker import get_tracker, clear_progress


def test_detect_hw_accel_modes():
    """Verify hardware acceleration detection with env overrides."""
    with patch.dict("os.environ", {"USE_HW_ACCEL": "none"}):
        assert detect_hw_accel() == "none"

    with patch.dict("os.environ", {"USE_HW_ACCEL": "cpu"}):
        assert detect_hw_accel() == "none"

    with patch.dict("os.environ", {"USE_HW_ACCEL": "nvenc"}):
        assert detect_hw_accel() == "nvenc"

    with patch.dict("os.environ", {"USE_HW_ACCEL": "videotoolbox"}):
        assert detect_hw_accel() == "videotoolbox"

    with patch.dict("os.environ", {"USE_HW_ACCEL": "qsv"}):
        assert detect_hw_accel() == "qsv"


def test_build_ffmpeg_cut_command_encoders():
    """Verify command structure for different encoders."""
    in_p = Path("/tmp/test_in.mp4")
    out_p = Path("/tmp/test_out.mp4")

    # CPU mode
    cmd_cpu = build_ffmpeg_cut_command(in_p, out_p, 5.0, 15.0, use_hw_accel=False)
    assert "-c:v" in cmd_cpu
    assert "libx264" in cmd_cpu
    assert "-preset" in cmd_cpu
    assert "veryfast" in cmd_cpu

    # With mocked nvenc
    with patch("backend.utils.video_processor.ACTIVE_HW_ACCEL", "nvenc"):
        cmd_nvenc = build_ffmpeg_cut_command(in_p, out_p, 5.0, 15.0, use_hw_accel=True)
        assert "h264_nvenc" in cmd_nvenc
        assert "-cq" in cmd_nvenc

    # With mocked videotoolbox
    with patch("backend.utils.video_processor.ACTIVE_HW_ACCEL", "videotoolbox"):
        cmd_vt = build_ffmpeg_cut_command(in_p, out_p, 5.0, 15.0, use_hw_accel=True)
        assert "h264_videotoolbox" in cmd_vt


def test_get_hardware_encoder_config_all_variants():
    """Verify encoder configurations return expected codec args."""
    with patch("backend.utils.video_processor.ACTIVE_HW_ACCEL", "nvenc"):
        cfg = VideoProcessor.get_hardware_encoder_config()
        assert cfg["encoder_type"] == "nvenc"
        assert "h264_nvenc" in cfg["codec_args"]
        assert cfg["use_hw"] is True

    with patch("backend.utils.video_processor.ACTIVE_HW_ACCEL", "videotoolbox"):
        cfg = VideoProcessor.get_hardware_encoder_config()
        assert cfg["encoder_type"] == "videotoolbox"
        assert "h264_videotoolbox" in cfg["codec_args"]

    with patch("backend.utils.video_processor.ACTIVE_HW_ACCEL", "qsv"):
        cfg = VideoProcessor.get_hardware_encoder_config()
        assert cfg["encoder_type"] == "qsv"
        assert "h264_qsv" in cfg["codec_args"]

    with patch("backend.utils.video_processor.ACTIVE_HW_ACCEL", "none"):
        cfg = VideoProcessor.get_hardware_encoder_config()
        assert cfg["encoder_type"] == "cpu"
        assert "libx264" in cfg["codec_args"]
        assert cfg["use_hw"] is False


def test_extract_clip_with_tracker_logging(tmp_path):
    """Verify extract_clip logs progress messages into tracker."""
    proj_id = "test-tracker-hw-proj"
    tracker = get_tracker(proj_id, "task-hw-1")

    in_video = tmp_path / "in.mp4"
    out_video = tmp_path / "out.mp4"
    in_video.write_bytes(b"dummy video data")

    # Mock subprocess.run to simulate successful copy or encode
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stderr = ""

    def side_effect(*args, **kwargs):
        out_video.write_bytes(b"fake encoded video exceeding 1024 bytes" * 50)
        return mock_res

    with patch("subprocess.run", side_effect=side_effect):
        success = VideoProcessor.extract_clip(
            input_video=in_video,
            output_path=out_video,
            start_time="00:00:00.000",
            end_time="00:00:10.000",
            tracker=tracker
        )
        assert success is True
        assert len(tracker.state.recent_logs) >= 1

    tracker.complete()
    clear_progress(proj_id)
