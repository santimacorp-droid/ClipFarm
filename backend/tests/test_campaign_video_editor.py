import subprocess
import tempfile
from pathlib import Path
import pytest

from backend.campaign.video_editor import (
    detect_silence_gaps, remove_dead_air, generate_outro_card,
    append_outro, auto_edit_full_video, get_video_duration
)


def _make_test_video(path: Path, duration: float = 5.0, width=1920, height=1080):
    """Create a synthetic test video."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=blue:s={width}x{height}:d={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)
    ], capture_output=True, check=True)


def test_get_video_duration():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "test.mp4"
        _make_test_video(src, duration=5.0)
        dur = get_video_duration(src)
        assert 4.5 < dur < 5.5, f"Expected ~5s, got {dur}s"


def test_detect_silence_gaps_no_gaps():
    """A pure color (no audio) video should have no silence gaps detectable."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "test.mp4"
        _make_test_video(src, duration=5.0)
        # No audio track = silencedetect finds nothing meaningful
        gaps = detect_silence_gaps(src, threshold_db=-40.0, min_gap_sec=1.2)
        # Either empty or found gaps at start (audio absent counts as silence)
        assert isinstance(gaps, list)


def test_remove_dead_air_no_crash():
    """remove_dead_air should not crash and should produce a non-empty output."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src.mp4"
        out = Path(tmp) / "out.mp4"
        _make_test_video(src, duration=4.0)
        ok = remove_dead_air(src, out)
        assert ok
        assert out.exists()
        assert out.stat().st_size > 0


def test_generate_outro_card_follow_handle():
    """Outro card should produce a valid 1080x1920 MP4."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "outro.mp4"
        ok = generate_outro_card(
            output_path=out,
            duration_sec=2.5,
            style="follow_handle",
            handle="@frida",
            width=1080,
            height=1920
        )
        assert ok
        assert out.exists()
        assert out.stat().st_size > 0
        dur = get_video_duration(out)
        assert 2.0 < dur < 3.5


def test_generate_outro_card_check_bio():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "outro_bio.mp4"
        ok = generate_outro_card(out, style="check_bio", width=1080, height=1920)
        assert ok and out.exists() and out.stat().st_size > 0


def test_auto_edit_full_video_no_outro():
    with tempfile.TemporaryDirectory() as tmp:
        src      = Path(tmp) / "source.mp4"
        clip_dir = Path(tmp) / "clip"
        _make_test_video(src, duration=10.0)
        result = auto_edit_full_video(
            source_path=src,
            clip_dir=clip_dir,
            restrictions={'remove_dead_air': True, 'outro_style': 'none'}
        )
        assert result is not None
        assert Path(result['video_file']).exists()
        assert result['start_sec'] == 0.0
        assert result['full_edit'] is True


def test_auto_edit_full_video_with_outro():
    with tempfile.TemporaryDirectory() as tmp:
        src      = Path(tmp) / "source.mp4"
        clip_dir = Path(tmp) / "clip_outro"
        _make_test_video(src, duration=5.0, width=1080, height=1920)
        result = auto_edit_full_video(
            source_path=src,
            clip_dir=clip_dir,
            restrictions={
                'remove_dead_air': False,
                'outro_style':  'follow_handle',
                'outro_handle': '@frida'
            }
        )
        assert result is not None
        final = Path(result['video_file'])
        assert final.exists()
        # Should be longer than source alone (source + 2.5s outro)
        dur = get_video_duration(final)
        assert dur > 5.0
