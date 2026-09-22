"""Tests for SmartFramingEngine and video layout generation."""

from pathlib import Path
from backend.utils.smart_framing import SmartFramingEngine, YUNET_MODEL_PATH


def test_yunet_model_file_exists():
    """Verify that the YuNet ONNX face detection model exists and is non-empty."""
    assert YUNET_MODEL_PATH.exists()
    assert YUNET_MODEL_PATH.stat().st_size > 100_000


def test_build_blurred_canvas_filter():
    """Verify enhanced blurred canvas filter graph string generation."""
    filtergraph = SmartFramingEngine.build_blurred_canvas_filter(
        in_w=1920,
        in_h=1080,
        canvas_w=1080,
        canvas_h=1920,
        input_label="0:v",
        output_label="v_base",
    )
    assert "boxblur=35:5" in filtergraph
    assert "eq=brightness=-0.12:contrast=0.95" in filtergraph
    assert "scale=1080:608:flags=lanczos[fg]" in filtergraph
    assert "[bg][fg]overlay=0:656[v_base]" in filtergraph


def test_build_podcast_split_filter():
    """Verify 2-speaker podcast split-screen filter graph generation."""
    filtergraph = SmartFramingEngine.build_podcast_split_filter(
        in_w=1920,
        in_h=1080,
        speaker1_cx=0.30,
        speaker2_cx=0.70,
        canvas_w=1080,
        canvas_h=1920,
        divider_thickness=4,
        input_label="0:v",
        output_label="v_base",
    )
    assert "scale=1080:958:flags=lanczos[top]" in filtergraph
    assert "scale=1080:958:flags=lanczos[bot]" in filtergraph
    assert "color=c=#1e1e1e:s=1080x1920" in filtergraph
    assert "overlay=0:962:shortest=1[v_base]" in filtergraph


def test_build_solo_smart_crop_filter():
    """Verify solo speaker face-centered crop filter generation."""
    filtergraph = SmartFramingEngine.build_solo_smart_crop_filter(
        in_w=1920,
        in_h=1080,
        speaker_cx=0.65,
        canvas_w=1080,
        canvas_h=1920,
        input_label="0:v",
        output_label="v_base",
    )
    assert "crop=608:1080" in filtergraph
    assert "scale=1080:1920:flags=lanczos[v_base]" in filtergraph


def test_analyze_video_nonexistent():
    """Verify graceful fallback for non-existent video path."""
    res = SmartFramingEngine.analyze_video_framing(Path("/tmp/nonexistent_video.mp4"))
    assert res["layout_type"] == "general"
    assert res["recommended_aspect_ratio"] == "9:16_blur"


def test_analyze_video_accepts_string_path():
    """Verify that string paths do not cause AttributeError: 'str' object has no attribute 'exists'."""
    res = SmartFramingEngine.analyze_video_framing("/tmp/nonexistent_video_string.mp4")
    assert res["layout_type"] == "general"
    assert res["recommended_aspect_ratio"] == "9:16_blur"


def test_framing_engine_caching():
    """Verify that repeated analysis returns cached result."""
    fake_path = "/tmp/fake_cached_video.mp4"
    res1 = SmartFramingEngine.analyze_video_framing(fake_path)
    res2 = SmartFramingEngine.analyze_video_framing(fake_path)
    assert res1 == res2
    assert fake_path in SmartFramingEngine._framing_cache


def test_build_black_header_canvas_filter():
    filt = SmartFramingEngine.build_black_header_canvas_filter(
        in_w=1920,
        in_h=1080,
        canvas_w=1080,
        canvas_h=1920,
        header_h=520,
        input_label="0:v",
        output_label="v_base"
    )
    assert "color=c=black:s=1080x1920" in filt
    assert "scale=1080:608" in filt
    assert "overlay=0:916:shortest=1[v_base]" in filt
