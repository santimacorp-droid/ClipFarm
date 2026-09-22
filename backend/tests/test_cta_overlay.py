import tempfile, subprocess
from pathlib import Path
from backend.utils.cta_overlay import (
    build_cta_filter, apply_cta_overlay, get_platform_cta, PLATFORM_CTA
)

def _make_clip(path: Path, w=1080, h=1920, duration=6.0):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=blue:s={w}x{h}:d={duration}",
        "-f", "lavfi", "-i", "aevalsrc=0:c=stereo:s=44100",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(path)
    ], capture_output=True, check=True)


def test_get_platform_cta_youtube():
    cta = get_platform_cta("youtube")
    assert cta["action"] == "Subscribe"
    assert "Subscribed" in cta["done"]

def test_get_platform_cta_tiktok():
    cta = get_platform_cta("tiktok")
    assert cta["action"] == "Follow"

def test_get_platform_cta_unknown_defaults():
    cta = get_platform_cta("snapchat")
    assert cta["action"] == "Follow"   # defaults to follow

def test_build_cta_filter_returns_string():
    vf = build_cta_filter(platform="tiktok", handle="@frida")
    assert isinstance(vf, str)
    assert "drawbox" in vf
    assert "drawtext" in vf

def test_build_cta_filter_youtube():
    vf = build_cta_filter(platform="youtube", video_duration=30.0)
    assert "Subscribe" in vf
    assert "Subscribed" in vf

def test_apply_cta_overlay_tiktok():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "clip.mp4"
        out = Path(tmp) / "clip_cta.mp4"
        _make_clip(src)
        ok = apply_cta_overlay(src, out, platform="tiktok", handle="@frida")
        assert ok, "apply_cta_overlay returned False"
        assert out.exists()
        assert out.stat().st_size > 0

def test_apply_cta_overlay_youtube():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "clip.mp4"
        out = Path(tmp) / "clip_cta_yt.mp4"
        _make_clip(src)
        ok = apply_cta_overlay(src, out, platform="youtube")
        assert ok
        assert out.exists()

def test_apply_cta_overlay_all_positions():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "clip.mp4"
        _make_clip(src)
        for pos in ["bottom_left", "bottom_center", "bottom_right"]:
            out = Path(tmp) / f"clip_cta_{pos}.mp4"
            ok = apply_cta_overlay(src, out, platform="instagram", position=pos)
            assert ok, f"Failed for position={pos}"
            assert out.exists()


def test_generate_multiplatform_cta_overlays():
    from backend.utils.cta_overlay import generate_multiplatform_cta_overlays
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "source_clip.mp4"
        _make_clip(src, duration=4.0)
        out_dir = Path(tmp) / "output"
        res = generate_multiplatform_cta_overlays(
            input_path=src,
            output_dir=out_dir,
            stem_prefix="highlight",
            handle="@creator",
            base_style="follow_tap",
            primary_platform="tiktok"
        )
        # Should have generated 4 platforms: tiktok, instagram, youtube_shorts, facebook
        for plat in ["tiktok", "instagram", "youtube_shorts", "facebook"]:
            assert plat in res, f"Platform {plat} missing in results"
            p = Path(res[plat])
            assert p.exists(), f"File {p} does not exist"
            assert p.stat().st_size > 0

        # And default highlight_cta.mp4
        default_cta = out_dir / "highlight_cta.mp4"
        assert default_cta.exists()

