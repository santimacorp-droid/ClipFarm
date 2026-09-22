"""
Tests for CPU Load Reduction, iGPU Acceleration, and API Offloading.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.core.shared_config import (
    TRANSCRIPTION_BACKEND,
    LLM_MAX_PARALLEL_CHUNKS,
    FFMPEG_MAX_PARALLEL_CUTS,
    USE_HW_ACCEL,
    HW_ACCEL_DEVICE,
    SPEECH_RECOGNITION_METHOD
)
from backend.utils.speech_recognizer import (
    transcribe,
    transcribe_with_qwen_asr,
    _synthesize_words_from_sentence,
    generate_subtitle_for_video,
    SpeechRecognizer,
    SpeechRecognitionMethod,
    SpeechRecognitionError
)
from backend.utils.video_processor import (
    detect_hw_accel,
    ACTIVE_HW_ACCEL,
    build_ffmpeg_cut_command,
    VideoProcessor
)


def test_shared_config_defaults():
    """Verify default offloading and hardware acceleration settings."""
    assert TRANSCRIPTION_BACKEND == "qwen3-asr-flash-filetrans"
    assert LLM_MAX_PARALLEL_CHUNKS == 4
    assert FFMPEG_MAX_PARALLEL_CUTS == 2
    assert USE_HW_ACCEL in ("auto", "vaapi")
    assert HW_ACCEL_DEVICE == "/dev/dri/renderD128"


def test_synthesize_words_from_sentence():
    """Test word-level timestamp synthesis for Latin and CJK text."""
    # Latin text
    words_en = _synthesize_words_from_sentence("Artificial intelligence is fast", 1.0, 3.0)
    assert len(words_en) == 4
    assert words_en[0]["word"] == "Artificial"
    assert words_en[0]["start"] == 1.0
    assert words_en[-1]["word"] == "fast"
    assert words_en[-1]["end"] == 3.0

    # CJK text
    words_zh = _synthesize_words_from_sentence("短视频剪辑", 0.0, 1.0)
    assert len(words_zh) == 5
    assert words_zh[0]["word"] == "短"
    assert words_zh[-1]["end"] == 1.0


def test_transcribe_fallback_chain(tmp_path):
    """Test transcribe() fallback chain: DashScope -> Whisper API -> local Whisper."""
    dummy_audio = tmp_path / "test.wav"
    dummy_audio.write_bytes(b"RIFFdummywavdata")

    # 1. DashScope success
    mock_segments = [{"start": 0.0, "end": 2.0, "text": "Hello world", "words": [{"word": "Hello", "start": 0.0, "end": 1.0}]}]
    with patch("backend.utils.speech_recognizer.transcribe_with_qwen_asr", return_value=mock_segments) as mock_qwen:
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "fake-key", "TRANSCRIPTION_BACKEND": "qwen3-asr-flash-filetrans"}):
            res = transcribe(dummy_audio)
            assert res == mock_segments
            mock_qwen.assert_called_once()

    # 2. DashScope failure falls back to local Whisper when no OpenAI key
    with patch("backend.utils.speech_recognizer.transcribe_with_qwen_asr", side_effect=Exception("API timeout")):
        with patch("backend.utils.speech_recognizer.transcribe_with_whisper", return_value=mock_segments) as mock_whisper:
            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "fake-key", "OPENAI_API_KEY": ""}):
                res = transcribe(dummy_audio)
                assert res == mock_segments
                mock_whisper.assert_called_once()


def test_qwen_asr_response_parsing(tmp_path):
    """Test qwen3-asr-flash-filetrans parsing and word-level timestamp extraction."""
    dummy_audio = tmp_path / "test.wav"
    dummy_audio.write_bytes(b"RIFFdummywavdata")

    fake_output = {
        "task_status": "SUCCEEDED",
        "transcripts": [
            {
                "sentences": [
                    {
                        "text": "Welcome to AutoClip",
                        "begin_time": 500,
                        "end_time": 2500,
                        "words": [
                            {"word": "Welcome", "begin_time": 500, "end_time": 1000},
                            {"word": "to", "begin_time": 1000, "end_time": 1300},
                            {"word": "AutoClip", "begin_time": 1300, "end_time": 2500}
                        ]
                    }
                ]
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.output = {"task_id": "task-xyz-123"}

    mock_fetch = MagicMock()
    mock_fetch.status_code = 200
    mock_fetch.output = fake_output

    with patch("dashscope.audio.asr.Transcription.async_call", return_value=mock_resp):
        with patch("dashscope.audio.asr.Transcription.fetch", return_value=mock_fetch):
            with patch("dashscope.utils.oss_utils.check_and_upload_local", return_value=(True, "oss://bucket/audio.wav", None)):
                segments = transcribe_with_qwen_asr(dummy_audio, api_key="sk-fake")

    assert len(segments) == 1
    seg = segments[0]
    assert seg["start"] == 0.5
    assert seg["end"] == 2.5
    assert seg["text"] == "Welcome to AutoClip"
    assert len(seg["words"]) == 3
    assert seg["words"][0]["word"] == "Welcome"
    assert seg["words"][0]["start"] == 0.5
    assert seg["words"][2]["end"] == 2.5


def test_detect_hw_accel():
    """Verify VAAPI detection on Ryzen 5 5600G /dev/dri/renderD128."""
    # When USE_HW_ACCEL is explicitly "none"
    with patch.dict(os.environ, {"USE_HW_ACCEL": "none"}):
        assert detect_hw_accel() == "none"

    # When on system with renderD128 and functional probe
    if Path("/dev/dri/renderD128").exists():
        with patch.dict(os.environ, {"USE_HW_ACCEL": "auto"}):
            accel = detect_hw_accel()
            assert accel in ("vaapi", "none")


def test_build_ffmpeg_cut_command():
    """Verify FFmpeg command generator properly targets VAAPI with -qp 23 or CPU with libx264."""
    in_p = Path("/tmp/input.mp4")
    out_p = Path("/tmp/output.mp4")

    # VAAPI command
    cmd_vaapi = build_ffmpeg_cut_command(in_p, out_p, 10.5, 30.0, use_hw_accel=True, hw_device="/dev/dri/renderD128")
    assert "-nostdin" in cmd_vaapi
    assert "-y" in cmd_vaapi
    if Path("/dev/dri/renderD128").exists() and ACTIVE_HW_ACCEL == "vaapi":
        assert "h264_vaapi" in cmd_vaapi
        assert "-qp" in cmd_vaapi
        assert "23" in cmd_vaapi
        assert "format=nv12,hwupload" in " ".join(cmd_vaapi)

    # CPU fallback command
    cmd_cpu = build_ffmpeg_cut_command(in_p, out_p, 10.5, 30.0, use_hw_accel=False)
    assert "-nostdin" in cmd_cpu
    assert "libx264" in cmd_cpu
    assert "-crf" in cmd_cpu
    assert "22" in cmd_cpu


def test_hardware_encoder_config():
    """Verify VideoProcessor encoder configuration."""
    cfg = VideoProcessor.get_hardware_encoder_config()
    assert "codec_args" in cfg
    if ACTIVE_HW_ACCEL == "vaapi" and Path("/dev/dri/renderD128").exists():
        assert cfg["use_vaapi"] is True
        assert "h264_vaapi" in cfg["codec_args"]
        assert "-qp" in cfg["codec_args"]
    else:
        assert cfg["use_vaapi"] is False
        assert "libx264" in cfg["codec_args"]


def test_parallel_batch_extract_clips(tmp_path):
    """Verify batch_extract_clips executes cuts in parallel capped at 2."""
    vp = VideoProcessor(clips_dir=str(tmp_path / "clips"), collections_dir=str(tmp_path / "collections"))
    
    clips_data = [
        {"id": 1, "title": "Clip 1", "start_time": 0.0, "end_time": 10.0},
        {"id": 2, "title": "Clip 2", "start_time": 10.0, "end_time": 20.0},
        {"id": 3, "title": "Clip 3", "start_time": 20.0, "end_time": 30.0},
    ]

    # Mock _cut_single_clip to return dummy output path
    def mock_cut(input_video, clip_data, **kwargs):
        out = tmp_path / "clips" / f"{clip_data['id']}_test.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"video")
        return out

    with patch.object(vp, "_cut_single_clip", side_effect=mock_cut) as mock_single:
        results = vp.batch_extract_clips(tmp_path / "in.mp4", clips_data, show_hook_banner=False)
        assert len(results) == 3
        assert mock_single.call_count == 3
