import tempfile
import subprocess
from pathlib import Path
from PIL import Image

from backend.utils.hook_overlay import (
    render_color_emoji_hook_banner,
    build_hook_overlay_filter,
    apply_hook_overlay
)

def _make_test_clip(path: Path, w=1080, h=1920, duration=5.0):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=darkblue:s={w}x{h}:d={duration}",
        "-f", "lavfi", "-i", "aevalsrc=0:c=stereo:s=44100",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(path)
    ], capture_output=True, check=True)


def test_render_color_emoji_hook_banner():
    with tempfile.TemporaryDirectory() as tmp:
        out_png = Path(tmp) / "banner.png"
        img = render_color_emoji_hook_banner(
            text="BRO SAID 'OH' WITH FULL CONFIDENCE 💀🔥",
            video_width=1080,
            video_height=1920,
            output_path=out_png
        )
        assert img is not None
        assert out_png.exists()
        assert out_png.stat().st_size > 0

        # Verify image format and properties (banner is sized to the stadium capsule)
        with Image.open(out_png) as loaded:
            assert loaded.mode == "RGBA"
            assert loaded.width <= 1080
            assert loaded.height > 0


def test_render_hook_banner_long_text_scaling():
    with tempfile.TemporaryDirectory() as tmp:
        out_png = Path(tmp) / "long_banner.png"
        img = render_color_emoji_hook_banner(
            text="THIS IS AN EXTREMELY LONG VIRAL HOOK TO TEST DYNAMIC SCALING 🤯🚨🌶️",
            video_width=1080,
            video_height=1920,
            output_path=out_png
        )
        assert img is not None
        assert out_png.exists()
        assert img.width <= int(1080 * 0.88) + 40


def test_build_hook_overlay_filter():
    filt = build_hook_overlay_filter(
        duration=4.2,
        fade_in=0.35,
        fade_out=0.40,
        y_offset=180,
        input_label="0:v",
        hook_input_idx=1,
        output_label="v_hook"
    )
    assert "fade=t=in" in filt
    assert "fade=t=out" in filt
    assert "overlay=" in filt
    assert "between(t,0,4.20)" in filt


def test_apply_hook_overlay():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "test_clip.mp4"
        out = Path(tmp) / "test_clip_hook.mp4"
        _make_test_clip(src, duration=5.0)

        ok = apply_hook_overlay(
            input_path=src,
            output_path=out,
            hook_text="THE MESSY HANDS TEST CAUSED TOTAL CHAOS 😭👨‍🍳"
        )
        assert ok is True
        assert out.exists()
        assert out.stat().st_size > 0

def test_render_hook_banner_with_keyword_highlight():
    with tempfile.TemporaryDirectory() as tmp:
        out_png = Path(tmp) / "highlight_banner.png"
        img = render_color_emoji_hook_banner(
            text="He asked what <hl>nobody dared to</hl> 🤐🎙️",
            video_width=1080,
            video_height=1920,
            category="podcast",
            output_path=out_png
        )
        assert img is not None
        assert out_png.exists()
        assert img.width > 200
        assert img.height > 40


def test_render_hook_banner_category_themes():
    with tempfile.TemporaryDirectory() as tmp:
        for cat in ["podcast", "interview", "vlog", "business", "tech_take", "entertainment"]:
            out_png = Path(tmp) / f"theme_{cat}.png"
            img = render_color_emoji_hook_banner(
                text=f"Testing Theme For {cat.title()} 🔥",
                video_width=1080,
                video_height=1920,
                category=cat,
                output_path=out_png
            )
            assert img is not None
            assert out_png.exists()


def test_render_black_header_hook_meme_style():
    from backend.utils.hook_overlay import render_black_header_hook, build_black_header_overlay_filter
    with tempfile.TemporaryDirectory() as tmp:
        out_png = Path(tmp) / "header_hook.png"
        # Test 1: Robin Williams style multi-line headline
        headline = "The day Robin Williams met Koko the Gorilla and made her laugh for the first time in six months"
        img = render_black_header_hook(
            text=headline,
            canvas_w=1080,
            header_h=520,
            output_path=out_png
        )
        assert img is not None
        assert out_png.exists()
        assert img.width == 1080
        assert img.height == 520

        # Test 2: Whiplash quote style
        out_png2 = Path(tmp) / "whiplash_header.png"
        whiplash_text = "There are no two words in the English language more harmful than \"good job\""
        img2 = render_black_header_hook(
            text=whiplash_text,
            canvas_w=1080,
            header_h=520,
            output_path=out_png2
        )
        assert img2 is not None
        assert out_png2.exists()
        assert img2.width == 1080
        assert img2.height == 520

        # Test 3: Overlay filter expression
        filt = build_black_header_overlay_filter(header_input_idx=1, input_label="0:v", output_label="v_hdr")
        assert "overlay=0:0:shortest=1[v_hdr]" in filt


def test_render_text_watermark():
    from backend.utils.watermark_processor import render_text_watermark, get_watermark_overlay_expr
    with tempfile.TemporaryDirectory() as tmp:
        out_png = Path(tmp) / "handle_wm.png"
        res = render_text_watermark(
            text="@autoclip",
            output_path=out_png,
            font_size=34,
            opacity=0.50
        )
        assert res is not None
        assert out_png.exists()
        assert out_png.stat().st_size > 0

        with Image.open(out_png) as img:
            assert img.mode == "RGBA"
            assert img.width > 150
            assert img.height > 30

        # Test position expression
        expr = get_watermark_overlay_expr("lower_center", 24)
        assert "(main_w-overlay_w)/2" in expr
        assert "main_h-overlay_h-24" in expr
