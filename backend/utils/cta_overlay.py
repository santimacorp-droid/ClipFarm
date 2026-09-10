"""
Studio-grade Animated CTA (Call-to-Action) overlay engine for short-form clips.
Platform-aware:
  - YouTube Shorts: Authentic YouTube Red play icon + Subscribe -> click compression -> dark pill + Subscribed checkmark + swinging bell chime
  - TikTok: Authentic chromatic aberration musical note + + Follow (TikTok Red #FE2C55) -> tap ripple -> dark pill + cyan checkmark + Following
  - Instagram: Authentic camera icon + sunset gradient Follow -> tap ripple -> dark pill + checkmark + Following
  - Facebook: Authentic circle 'f' + Royal Blue #1877F2 Follow -> click -> dark pill + checkmark + Following

Supports two visual styles:
  - 'pill' (default): Modern standalone interactive action button
  - 'card': Frosted glass floating channel badge with @handle and action button
"""

import os
import math
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# ─── Supported Platforms & Metadata ──────────────────────────────────────────

SUPPORTED_CTA_PLATFORMS = ["tiktok", "instagram", "youtube_shorts", "facebook"]

PLATFORM_CTA = {
    "youtube":        {"action": "Subscribe", "done": "Subscribed ✓", "color": "0xff0000", "done_color": "0xcc0000"},
    "youtube_shorts": {"action": "Subscribe", "done": "Subscribed ✓", "color": "0xff0000", "done_color": "0xcc0000"},
    "tiktok":         {"action": "Follow",    "done": "Following ✓",  "color": "0xfe2c55", "done_color": "0x1a1a2e"},
    "instagram":      {"action": "Follow",    "done": "Following ✓",  "color": "0x833ab4", "done_color": "0xe1306c"},
    "facebook":       {"action": "Follow",    "done": "Following ✓",  "color": "0x1877f2", "done_color": "0x166fe5"},
    "default":        {"action": "Follow",    "done": "Following ✓",  "color": "0x2D6BFF", "done_color": "0x1a56d6"},
}

def get_platform_cta(platform: str) -> dict:
    """Return CTA text and color mapping for a platform."""
    key = str(platform or "default").lower().replace("-", "_").replace(" ", "_")
    return PLATFORM_CTA.get(key, PLATFORM_CTA["default"])


# ─── Font Resolution ─────────────────────────────────────────────────────────

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load system TrueType font with graceful fallback."""
    for fp in FONT_CANDIDATES:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def _find_font() -> str:
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return f
    return ""


# ─── Vector Icon Renderers (Pillow) ──────────────────────────────────────────

def draw_youtube_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> int:
    """Draw official YouTube play button logo with rounded rectangle and white triangle."""
    w = int(size * 1.36)
    h = size
    radius = int(size * 0.28)
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=radius, fill=(255, 0, 0, 255))
    cx, cy = x + w // 2, y + h // 2
    tw = int(size * 0.32)
    th = int(size * 0.36)
    tri = [(cx - tw // 2 + 1, cy - th // 2), (cx - tw // 2 + 1, cy + th // 2), (cx + tw // 2 + 2, cy)]
    draw.polygon(tri, fill=(255, 255, 255, 255))
    return w

def draw_tiktok_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> int:
    """Draw authentic TikTok musical note icon with chromatic aberration (cyan & magenta)."""
    r = size // 2
    cx, cy = x + r, y + r
    draw.ellipse([(x, y), (x + size, y + size)], fill=(16, 18, 24, 255), outline=(255, 255, 255, 45), width=1)
    
    def draw_note(offset_x, offset_y, color):
        ox, oy = cx + offset_x, cy + offset_y
        draw.rectangle([(ox + 1, oy - 12), (ox + 5, oy + 4)], fill=color)
        draw.polygon([(ox + 5, oy - 12), (ox + 13, oy - 8), (ox + 13, oy - 4), (ox + 5, oy - 8)], fill=color)
        draw.ellipse([(ox - 8, oy + 1), (ox + 3, oy + 11)], fill=color)

    draw_note(-2, 0, (0, 242, 254, 230))  # Cyan glow
    draw_note(2, 0, (254, 44, 85, 230))   # TikTok red/pink
    draw_note(0, 0, (255, 255, 255, 255)) # White foreground
    return size

def draw_instagram_icon(canvas: Image.Image, x: int, y: int, size: int) -> int:
    """Draw authentic Instagram camera icon with sunset gradient."""
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(grad)
    for i in range(size):
        ratio = i / float(size)
        if ratio < 0.5:
            r2 = ratio * 2
            r_c = int(131 + (253 - 131) * r2)
            g_c = int(58 + (29 - 58) * r2)
            b_c = int(180 + (29 - 180) * r2)
        else:
            r2 = (ratio - 0.5) * 2
            r_c = int(253 + (252 - 253) * r2)
            g_c = int(29 + (176 - 29) * r2)
            b_c = int(29 + (69 - 29) * r2)
        g_draw.line([(0, i), (size, i)], fill=(r_c, g_c, b_c, 255))
    
    mask = Image.new("L", (size, size), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.rounded_rectangle([(0, 0), (size, size)], radius=int(size * 0.28), fill=255)
    
    cam = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(cam)
    pad = int(size * 0.20)
    c_draw.rounded_rectangle([(pad, pad), (size - pad, size - pad)], radius=int(size * 0.20), outline=(255, 255, 255, 255), width=max(2, int(size * 0.08)))
    c_draw.ellipse([(size//2 - int(size*0.17), size//2 - int(size*0.17)), (size//2 + int(size*0.17), size//2 + int(size*0.17))], outline=(255, 255, 255, 255), width=max(2, int(size * 0.08)))
    dot_r = max(1, int(size * 0.04))
    c_draw.ellipse([(size - pad - dot_r*3, pad + dot_r), (size - pad - dot_r, pad + dot_r*3)], fill=(255, 255, 255, 255))

    icon_img = Image.composite(grad, Image.new("RGBA", (size, size), (0, 0, 0, 0)), mask)
    icon_img.alpha_composite(cam)
    canvas.alpha_composite(icon_img, (x, y))
    return size

def draw_facebook_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> int:
    """Draw authentic Facebook circle 'f' icon."""
    draw.ellipse([(x, y), (x + size, y + size)], fill=(24, 119, 242, 255))
    f_font = _get_font(int(size * 0.84), bold=True)
    draw.text((x + int(size * 0.36), y + int(size * 0.02)), "f", font=f_font, fill=(255, 255, 255, 255))
    return size

def draw_bell_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, angle_deg: float = 0.0):
    """Draw animated notification bell with angle rotation."""
    dim = size * 2
    bell_canvas = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(bell_canvas)
    bx, by = dim // 2, dim // 2
    w = int(size * 0.65)
    h = int(size * 0.72)
    # Top loop
    b_draw.ellipse([(bx - 3, by - h//2 - 6), (bx + 3, by - h//2)], fill=(255, 255, 255, 255))
    # Dome
    b_draw.polygon([
        (bx - w//3, by - h//2),
        (bx + w//3, by - h//2),
        (bx + w//2, by + h//2 - 6),
        (bx + w//2 + 4, by + h//2),
        (bx - w//2 - 4, by + h//2),
        (bx - w//2 - 4, by + h//2 - 6)
    ], fill=(255, 255, 255, 255))
    # Clapper
    b_draw.ellipse([(bx - 4, by + h//2 + 1), (bx + 4, by + h//2 + 7)], fill=(255, 255, 255, 255))
    
    if abs(angle_deg) > 0.1:
        bell_canvas = bell_canvas.rotate(angle_deg, resample=Image.BICUBIC, center=(dim // 2, dim // 2))
    
    draw.bitmap((x - dim // 2, y - dim // 2), bell_canvas)

def draw_checkmark(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color=(255, 255, 255, 255)):
    """Draw crisp anti-aliased checkmark."""
    pts = [
        (x, y + int(size * 0.48)),
        (x + int(size * 0.38), y + size),
        (x + size, y)
    ]
    draw.line(pts, fill=color, width=max(2, int(size * 0.22)), joint="curve")

def draw_cursor(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 36):
    """Draw modern vector arrow cursor with soft outline."""
    poly = [
        (x, y),
        (x, y + int(size * 0.85)),
        (x + int(size * 0.24), y + int(size * 0.65)),
        (x + int(size * 0.48), y + int(size * 1.05)),
        (x + int(size * 0.62), y + int(size * 0.98)),
        (x + int(size * 0.38), y + int(size * 0.58)),
        (x + int(size * 0.68), y + int(size * 0.58))
    ]
    draw.polygon(poly, fill=(255, 255, 255, 255), outline=(15, 15, 20, 255), width=2)


# ─── CTA Card & Pill Renderers ──────────────────────────────────────────────

def render_pill_button(
    platform: str = "tiktok",
    handle: str = "",
    state: str = "initial",
    scale: float = 1.0,
    bell_angle: float = 0.0
) -> Image.Image:
    """
    Render clean standalone pill button (e.g. [ (f) Follow @Handle ] -> [ ✓ Following @Handle ]).
    """
    btn_font = _get_font(26, bold=True)
    clean_handle = handle.strip()
    if clean_handle and not clean_handle.startswith("@"):
        clean_handle = f"@{clean_handle}"

    icon_size = 40
    base_h = 76
    icon_y = (base_h - icon_size) // 2
    icon_x = 22

    if state == "initial":
        if platform in ("youtube", "youtube_shorts"):
            action_text = f"Subscribe {clean_handle}".strip()
            icon_w = int(icon_size * 1.36)
        elif platform == "tiktok":
            action_text = f"+ Follow {clean_handle}".strip()
            icon_w = icon_size
        else:
            action_text = f"Follow {clean_handle}".strip()
            icon_w = icon_size
    else:
        if platform in ("youtube", "youtube_shorts"):
            action_text = f"Subscribed {clean_handle}".strip()
            icon_w = 28
        else:
            action_text = f"Following {clean_handle}".strip()
            icon_w = 28

    # Calculate dynamic width to fit handle smoothly
    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)
    t_bbox = dummy_draw.textbbox((0, 0), action_text, font=btn_font)
    tw = t_bbox[2] - t_bbox[0]

    min_w = 340 if platform in ("youtube", "youtube_shorts") else 290
    right_pad = 26 + (42 if (state != "initial" and platform in ("youtube", "youtube_shorts")) else 0)
    base_w = max(min_w, icon_x + icon_w + 16 + tw + right_pad)

    img = Image.new("RGBA", (base_w, base_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if state == "initial":
        if platform in ("youtube", "youtube_shorts"):
            draw.rounded_rectangle([(0, 0), (base_w, base_h)], radius=38, fill=(255, 0, 0, 255))
            draw_youtube_icon(draw, icon_x, icon_y, icon_size)
            draw.text((icon_x + icon_w + 16, base_h // 2 - 17), action_text, font=btn_font, fill=(255, 255, 255, 255))
        elif platform == "tiktok":
            draw.rounded_rectangle([(0, 0), (base_w, base_h)], radius=38, fill=(254, 44, 85, 255))
            draw_tiktok_icon(draw, icon_x, icon_y, icon_size)
            draw.text((icon_x + icon_w + 16, base_h // 2 - 17), action_text, font=btn_font, fill=(255, 255, 255, 255))
        elif platform == "instagram":
            # Sunset gradient pill
            grad = Image.new("RGBA", (base_w, base_h), (0, 0, 0, 0))
            g_draw = ImageDraw.Draw(grad)
            for px in range(base_w):
                ratio = px / float(base_w)
                r_c = int(131 + (253 - 131) * ratio)
                g_c = int(58 + (29 - 58) * ratio)
                b_c = int(180 + (29 - 180) * ratio)
                g_draw.line([(px, 0), (px, base_h)], fill=(r_c, g_c, b_c, 255))
            mask = Image.new("L", (base_w, base_h), 0)
            m_draw = ImageDraw.Draw(mask)
            m_draw.rounded_rectangle([(0, 0), (base_w, base_h)], radius=38, fill=255)
            img = Image.composite(grad, img, mask)
            draw = ImageDraw.Draw(img)
            draw_instagram_icon(img, icon_x, icon_y, icon_size)
            draw.text((icon_x + icon_size + 16, base_h // 2 - 17), action_text, font=btn_font, fill=(255, 255, 255, 255))
        else:
            # Facebook Royal Blue
            draw.rounded_rectangle([(0, 0), (base_w, base_h)], radius=38, fill=(24, 119, 242, 255))
            draw_facebook_icon(draw, icon_x, icon_y, icon_size)
            draw.text((icon_x + icon_size + 16, base_h // 2 - 17), action_text, font=btn_font, fill=(255, 255, 255, 255))
    else:
        # Activated state: dark glass pill with checkmark
        draw.rounded_rectangle([(0, 0), (base_w, base_h)], radius=38, fill=(22, 24, 32, 240), outline=(255, 255, 255, 45), width=2)
        check_col = (0, 242, 254, 255) if platform == "tiktok" else (255, 255, 255, 255)
        # Checkmark
        pts = [(icon_x + 6, base_h//2 + 3), (icon_x + 14, base_h//2 + 11), (icon_x + 28, base_h//2 - 7)]
        draw.line(pts, fill=check_col, width=4, joint="curve")
        draw.text((icon_x + 36 + 14, base_h // 2 - 17), action_text, font=btn_font, fill=(255, 255, 255, 255))

        # For YouTube: add notification bell on the right
        if platform in ("youtube", "youtube_shorts"):
            bell_x = base_w - 38
            bell_y = base_h // 2
            draw_bell_icon(draw, bell_x, bell_y, 22, angle_deg=bell_angle)

    if abs(scale - 1.0) > 0.01:
        new_w = max(1, int(base_w * scale))
        new_h = max(1, int(base_h * scale))
        img = img.resize((new_w, new_h), Image.BILINEAR)

    return img


def render_cta_card(
    platform: str = "tiktok",
    handle: str = "",
    state: str = "initial",
    scale: float = 1.0,
    bell_angle: float = 0.0
) -> Image.Image:
    """
    Render channel badge card: [ (Platform Logo)  @Handle  (Action Button) ].
    """
    font_main = _get_font(28, bold=True)
    clean_h = handle.strip()
    display_handle = clean_h if clean_h.startswith("@") else f"@{clean_h}" if clean_h else "@Channel"

    icon_size = 50
    card_h = 104
    icon_y = (card_h - icon_size) // 2
    icon_x = 24
    if platform in ("youtube", "youtube_shorts"):
        icon_w = int(icon_size * 1.36)
    else:
        icon_w = icon_size

    btn_w = 180 if platform in ("youtube", "youtube_shorts") else 150
    btn_h = 58
    btn_font = _get_font(22, bold=True)

    # Dynamic card width to guarantee no handle truncation
    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)
    h_bbox = dummy_draw.textbbox((0, 0), display_handle, font=font_main)
    handle_w = h_bbox[2] - h_bbox[0]

    min_card_w = 600
    card_w = max(min_card_w, icon_x + icon_w + 20 + handle_w + 28 + btn_w + 24)

    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    # 1. Frosted dark glass background with subtle light border
    draw.rounded_rectangle(
        [(0, 0), (card_w, card_h)],
        radius=28,
        fill=(16, 17, 24, 235),
        outline=(255, 255, 255, 45),
        width=2
    )

    # 2. Platform Logo
    if platform in ("youtube", "youtube_shorts"):
        draw_youtube_icon(draw, icon_x, icon_y, icon_size)
    elif platform == "tiktok":
        draw_tiktok_icon(draw, icon_x, icon_y, icon_size)
    elif platform == "instagram":
        draw_instagram_icon(card, icon_x, icon_y, icon_size)
    else:
        draw_facebook_icon(draw, icon_x, icon_y, icon_size)

    # 3. Handle / Channel Name
    text_x = icon_x + icon_w + 18
    text_y = card_h // 2 - 16
    draw.text((text_x, text_y), display_handle, font=font_main, fill=(255, 255, 255, 255))

    # 4. Action Button on Right
    btn_x = card_w - btn_w - 22
    btn_y = (card_h - btn_h) // 2

    if state == "initial":
        if platform in ("youtube", "youtube_shorts"):
            draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=29, fill=(255, 0, 0, 255))
            bbox = draw.textbbox((0, 0), "Subscribe", font=btn_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((btn_x + (btn_w - tw)//2, btn_y + (btn_h - th)//2 - 2), "Subscribe", font=btn_font, fill=(255, 255, 255, 255))
        elif platform == "tiktok":
            draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=29, fill=(254, 44, 85, 255))
            bbox = draw.textbbox((0, 0), "+ Follow", font=btn_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((btn_x + (btn_w - tw)//2, btn_y + (btn_h - th)//2 - 2), "+ Follow", font=btn_font, fill=(255, 255, 255, 255))
        elif platform == "instagram":
            draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=29, fill=(0, 149, 246, 255))
            bbox = draw.textbbox((0, 0), "Follow", font=btn_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((btn_x + (btn_w - tw)//2, btn_y + (btn_h - th)//2 - 2), "Follow", font=btn_font, fill=(255, 255, 255, 255))
        else:
            draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=29, fill=(24, 119, 242, 255))
            bbox = draw.textbbox((0, 0), "Follow", font=btn_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((btn_x + (btn_w - tw)//2, btn_y + (btn_h - th)//2 - 2), "Follow", font=btn_font, fill=(255, 255, 255, 255))
    else:
        # Transformed state
        draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=29, fill=(45, 48, 58, 255), outline=(255, 255, 255, 40), width=1)
        label = "Subscribed" if platform in ("youtube", "youtube_shorts") else "Following"
        bbox = draw.textbbox((0, 0), label, font=btn_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        check_color = (0, 242, 254, 255) if platform == "tiktok" else (255, 255, 255, 255)
        # Checkmark
        cm_x = btn_x + 18
        cm_y = btn_y + 20
        pts = [(cm_x, cm_y + 8), (cm_x + 6, cm_y + 14), (cm_x + 16, cm_y)]
        draw.line(pts, fill=check_color, width=3, joint="curve")
        draw.text((btn_x + 42, btn_y + (btn_h - th)//2 - 2), label, font=btn_font, fill=(255, 255, 255, 240))

        if platform in ("youtube", "youtube_shorts"):
            draw_bell_icon(draw, btn_x + btn_w - 24, btn_y + btn_h // 2, 18, angle_deg=bell_angle)

    if abs(scale - 1.0) > 0.01:
        new_w = max(1, int(card_w * scale))
        new_h = max(1, int(card_h * scale))
        card = card.resize((new_w, new_h), Image.BILINEAR)

    return card


# ─── Static Watermark Badge Generator ────────────────────────────────────────

def generate_watermark_canvas(
    platform: str = "facebook",
    handle: str = "",
    style: str = "pill",
    video_width: int = 1080,
    video_height: int = 1920,
    position: str = "lower_middle"
) -> Image.Image:
    """
    Generate a full video-size transparent RGBA image with the initial CTA badge
    and drop shadow positioned exactly where the CTA animation will play.
    Serves as persistent anti-theft watermark across the video.
    """
    is_card = style in ("card", "badge")
    if is_card:
        widget = render_cta_card(platform, handle, "initial")
    else:
        widget = render_pill_button(platform, handle, "initial")

    ww, wh = widget.size
    max_w = int(video_width * 0.80)
    if ww > max_w:
        resp_scale = max_w / float(ww)
        ww = int(ww * resp_scale)
        wh = int(wh * resp_scale)
        widget = widget.resize((ww, wh), Image.BILINEAR)

    pos = str(position or "lower_middle").lower().replace("-", "_")
    if pos in ("lower_middle", "lower_center"):
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.62)
    elif pos == "lower_third":
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.68)
    elif pos == "center":
        target_x = (video_width - ww) // 2
        target_y = (video_height - wh) // 2
    elif pos == "bottom_center":
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.82)
    elif pos == "bottom_left":
        target_x = int(video_width * 0.08)
        target_y = int(video_height * 0.62)
    elif pos == "bottom_right":
        target_x = video_width - ww - int(video_width * 0.08)
        target_y = int(video_height * 0.62)
    else:
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.62)

    canvas = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    # Soft drop shadow
    shadow_box = Image.new("RGBA", (ww + 30, wh + 30), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_box)
    s_draw.rounded_rectangle([(15, 15), (ww + 15, wh + 15)], radius=36, fill=(0, 0, 0, 95))
    shadow_blurred = shadow_box.filter(ImageFilter.GaussianBlur(12))
    canvas.alpha_composite(shadow_blurred, (target_x - 15, target_y - 5))
    canvas.alpha_composite(widget, (target_x, target_y))
    return canvas


# ─── Animation Builder (Procedural RGBA Sequence -> MOV) ─────────────────────

def build_cta_animation_clip(
    platform: str = "tiktok",
    handle: str = "",
    style: str = "pill",
    video_width: int = 1080,
    video_height: int = 1920,
    position: str = "lower_middle",
    output_mov_path: Optional[Path] = None,
    fps: int = 30,
    duration_sec: float = 3.5,
    as_watermark: bool = False
) -> Path:
    """
    Generate a 3.5-second transparent QuickTime Animation (qtrle) clip with
    eased slide-in or seamless watermark stationing, vector cursor click, button compression,
    and checkmark/bell activation.
    """
    safe_h = handle.replace("@", "").replace("/", "_").strip() or "nohandle"
    safe_plat = platform.lower().replace("-", "_")
    safe_style = "card" if style in ("card", "badge") else "pill"
    safe_pos = position.lower().replace("-", "_")
    safe_mode = "wm" if as_watermark else "slide"

    if output_mov_path is None:
        cache_dir = Path("data/assets/cta_templates")
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_mov_path = cache_dir / f"cta_v5_{safe_plat}_{safe_style}_{safe_pos}_{safe_h}_{safe_mode}_{video_width}x{video_height}.mov"

    if output_mov_path.exists() and output_mov_path.stat().st_size > 1000:
        return output_mov_path

    total_frames = int(fps * duration_sec)
    tmp_frames_dir = Path(f"/tmp/cta_build_{os.getpid()}_{platform}_{safe_mode}")
    tmp_frames_dir.mkdir(parents=True, exist_ok=True)

    # Normalize style
    is_card = style in ("card", "badge")

    # Render base components with handle
    if is_card:
        widget_init = render_cta_card(platform, handle, "initial")
        widget_act  = render_cta_card(platform, handle, "active")
    else:
        widget_init = render_pill_button(platform, handle, "initial")
        widget_act  = render_pill_button(platform, handle, "active")

    ww, wh = widget_init.size
    max_w = int(video_width * 0.80)
    if ww > max_w:
        resp_scale = max_w / float(ww)
        ww = int(ww * resp_scale)
        wh = int(wh * resp_scale)
        widget_init = widget_init.resize((ww, wh), Image.BILINEAR)
        widget_act  = widget_act.resize((ww, wh), Image.BILINEAR)

    # Determine target (x, y) coordinates based on position
    pos = str(position or "lower_middle").lower().replace("-", "_")
    if pos in ("lower_middle", "lower_center"):
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.62)
    elif pos == "lower_third":
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.68)
    elif pos == "center":
        target_x = (video_width - ww) // 2
        target_y = (video_height - wh) // 2
    elif pos == "bottom_center":
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.82)
    elif pos == "bottom_left":
        target_x = int(video_width * 0.08)
        target_y = int(video_height * 0.62)
    elif pos == "bottom_right":
        target_x = video_width - ww - int(video_width * 0.08)
        target_y = int(video_height * 0.62)
    else:
        target_x = (video_width - ww) // 2
        target_y = int(video_height * 0.62)

    btn_offset = int((50 if not is_card else 90) * (ww / 600.0))
    cursor_target_x = target_x + ww - max(30, btn_offset)
    cursor_target_y = target_y + wh // 2 + 10

    for i in range(total_frames):
        t = i / float(fps)
        frame = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))

        # 1. Entrance position (stationed if watermark mode; slide up if standalone)
        if not as_watermark and t < 0.4:
            prog = t / 0.4
            ease = 1.0 - math.pow(1.0 - prog, 3)
            curr_y = int(video_height - (video_height - target_y) * ease)
        else:
            curr_y = target_y

        # 2. Click compression & state
        bell_rot = 0.0
        if t < 1.8:
            curr_widget = widget_init
            scale = 1.0
        elif t < 2.0:
            # Click compression
            curr_widget = widget_init
            scale = 0.93
        else:
            # Activated state
            if platform in ("youtube", "youtube_shorts") and (2.1 <= t <= 2.8):
                bell_t = (t - 2.1) / 0.7
                bell_rot = math.sin(bell_t * math.pi * 6) * 16.0 * (1.0 - bell_t)

            if is_card:
                curr_widget = render_cta_card(platform, handle, "active", bell_angle=bell_rot)
            else:
                curr_widget = render_pill_button(platform, handle, "active", bell_angle=bell_rot)
            scale = 1.0

        if abs(scale - 1.0) > 0.01:
            cw, ch = int(ww * scale), int(wh * scale)
            rendered_widget = curr_widget.resize((cw, ch), Image.BILINEAR)
            px = target_x + (ww - cw) // 2
            py = curr_y + (wh - ch) // 2
        else:
            rendered_widget = curr_widget
            px = target_x
            py = curr_y

        # Add soft drop shadow
        shadow_box = Image.new("RGBA", (ww + 30, wh + 30), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_box)
        s_draw.rounded_rectangle([(15, 15), (ww + 15, wh + 15)], radius=36, fill=(0, 0, 0, 95))
        shadow_blurred = shadow_box.filter(ImageFilter.GaussianBlur(12))
        frame.alpha_composite(shadow_blurred, (px - 15, py - 5))

        # Composite widget
        frame.alpha_composite(rendered_widget, (px, py))

        # 3. Vector Cursor overlay
        if 1.0 <= t <= 2.4:
            if t < 1.7:
                c_prog = (t - 1.0) / 0.7
                c_ease = 1.0 - math.pow(1.0 - c_prog, 2)
                cx = int(cursor_target_x + 120 - 120 * c_ease)
                cy = int(cursor_target_y + 160 - 160 * c_ease)
            elif t <= 2.0:
                cx = cursor_target_x
                cy = cursor_target_y
            else:
                c_prog = (t - 2.0) / 0.4
                cx = int(cursor_target_x + 60 * c_prog)
                cy = int(cursor_target_y + 60 * c_prog)

            c_draw = ImageDraw.Draw(frame)
            draw_cursor(c_draw, cx, cy, size=34)

        frame.save(tmp_frames_dir / f"frame_{i:04d}.png")

    # Encode sequence to transparent QuickTime Animation (.mov)
    output_mov_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", str(tmp_frames_dir / "frame_%04d.png"),
        "-c:v", "qtrle",
        str(output_mov_path)
    ]
    res = subprocess.run(cmd, capture_output=True)

    # Cleanup temporary frame images
    try:
        import shutil
        shutil.rmtree(tmp_frames_dir, ignore_errors=True)
    except Exception:
        pass

    if res.returncode == 0 and output_mov_path.exists():
        logger.info(f"Generated CTA animation template: {output_mov_path}")
        return output_mov_path
    else:
        logger.error(f"Failed to encode CTA animation MOV: {res.stderr.decode('utf-8', errors='ignore')[-300:]}")
        return output_mov_path


# ─── Legacy Filter String Fallback ───────────────────────────────────────────

def build_cta_filter(
    video_width:    int   = 1080,
    video_height:   int   = 1920,
    platform:       str   = "tiktok",
    handle:         str   = "",
    style:          str   = "pill",
    position:       str   = "lower_middle",
    start_time:     Optional[float] = None,
    video_duration: float = 30.0,
    watermark:      bool  = True,
) -> str:
    """
    Fallback FFmpeg filter string builder (preserves unit test compatibility).
    """
    font   = _find_font()
    cta    = get_platform_cta(platform)
    action = cta["action"]
    done   = cta["done"]
    color  = cta["color"]

    if style == "subscribe_click" or platform in ("youtube", "youtube_shorts"):
        action = "Subscribe"
        done = "Subscribed ✓"
        color = "0xff0000"

    clean_h = handle.strip()
    if clean_h:
        display_h = clean_h if clean_h.startswith("@") else f"@{clean_h}"
        action = f"{action} {display_h}"
        done = f"{done} {display_h}"

    t0 = max(0.0, float(start_time)) if start_time is not None else max(1.0, video_duration - 3.5)
    btn_w = int(video_width * 0.45) if clean_h else int(video_width * 0.35)
    btn_h = int(video_height * 0.05)
    bx = f"({video_width}-{btn_w})/2"
    by = f"({video_height}*0.62)"

    font_arg = f":fontfile='{font}'" if font else ""
    filters = []
    if watermark and t0 > 0:
        filters.append(f"drawbox=x='{bx}':y='{by}':w='{btn_w}':h='{btn_h}':color={color}:t=fill:enable='between(t,0,{t0})'")
        filters.append(f"drawtext=text='{action}':fontsize=32{font_arg}:fontcolor=white:x='({bx})+({btn_w}/2-tw/2)':y='({by})+({btn_h}/2-th/2)':enable='between(t,0,{t0})'")

    filters.extend([
        f"drawbox=x='{bx}':y='{by}':w='{btn_w}':h='{btn_h}':color={color}:t=fill:enable='between(t,{t0},{t0+1.5})'",
        f"drawbox=x='{bx}':y='{by}':w='{btn_w}':h='{btn_h}':color=0x1a1a2e:t=fill:enable='between(t,{t0+1.5},{t0+3.5})'",
        f"drawtext=text='{action}':fontsize=32{font_arg}:fontcolor=white:x='({bx})+({btn_w}/2-tw/2)':y='({by})+({btn_h}/2-th/2)':enable='between(t,{t0},{t0+1.5})'",
        f"drawtext=text='{done}':fontsize=32{font_arg}:fontcolor=white:x='({bx})+({btn_w}/2-tw/2)':y='({by})+({btn_h}/2-th/2)':enable='between(t,{t0+1.5},{t0+3.5})'"
    ])
    return ",".join(filters)


# ─── Main Video Application Function ─────────────────────────────────────────

def apply_cta_overlay(
    input_path:     Path,
    output_path:    Path,
    platform:       str             = "tiktok",
    handle:         str             = "",
    style:          str             = "pill",
    position:       str             = "lower_middle",
    start_time:     Optional[float] = None,
    video_width:    Optional[int]   = None,
    video_height:   Optional[int]   = None,
    video_duration: Optional[float] = None,
    watermark:      bool            = True,
) -> bool:
    """
    Apply studio-grade animated CTA overlay with persistent anti-theft watermark to a clip.
    - Throughout the clip (t=0 to t_start): displays watermark badge with handle at lower middle.
    - At final CTA (t_start to end): animates vector cursor click and transforms into Following.
    """
    input_path  = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        logger.error(f"apply_cta_overlay: input_path not found: {input_path}")
        return False

    w = video_width or 1080
    h = video_height or 1920
    duration = video_duration or 30.0

    if not video_duration or not video_width or not video_height:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration:stream=width,height",
                "-of", "json", str(input_path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0 and res.stdout:
                import json
                info = json.loads(res.stdout)
                if "format" in info and "duration" in info["format"] and not video_duration:
                    duration = float(info["format"]["duration"])
                if "streams" in info:
                    for s in info["streams"]:
                        if s.get("width") and s.get("height"):
                            if not video_width:
                                w = int(s["width"])
                            if not video_height:
                                h = int(s["height"])
                            break
        except Exception as e:
            logger.debug(f"ffprobe in apply_cta_overlay: {e}")

    # Normalize timing: overlay in final 3.5 seconds
    anim_duration = 3.5
    if start_time is None:
        t_start = max(0.0, duration - anim_duration)
    else:
        t_start = max(0.0, float(start_time))
    t_end = min(duration, t_start + anim_duration)

    # Normalize style: pill or card
    chosen_style = "card" if style in ("card", "badge") else "pill"
    is_wm = watermark and (t_start > 0.1)

    # Build or fetch transparent animated overlay MOV
    overlay_mov = build_cta_animation_clip(
        platform=platform,
        handle=handle,
        style=chosen_style,
        video_width=w,
        video_height=h,
        position=position,
        duration_sec=anim_duration,
        as_watermark=is_wm
    )

    # Generate static watermark PNG if watermark mode is enabled
    wm_png_path = None
    tmp_wm_dir = None
    if is_wm:
        try:
            tmp_wm_dir = Path(f"/tmp/cta_wm_{os.getpid()}")
            tmp_wm_dir.mkdir(parents=True, exist_ok=True)
            safe_h = handle.replace("@", "").replace("/", "_").strip() or "nohandle"
            wm_png_path = tmp_wm_dir / f"wm_{w}x{h}_{safe_h}_{position}.png"
            wm_canvas = generate_watermark_canvas(
                platform=platform,
                handle=handle,
                style=chosen_style,
                video_width=w,
                video_height=h,
                position=position
            )
            wm_canvas.save(wm_png_path)
        except Exception as wm_err:
            logger.warning(f"Failed to generate static watermark canvas: {wm_err}")
            wm_png_path = None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    vaapi_device = "/dev/dri/renderD128"
    can_use_vaapi = os.path.exists(vaapi_device) and os.access(vaapi_device, os.W_OK | os.R_OK)

    applied = False
    has_wm = (wm_png_path is not None and wm_png_path.exists())

    if overlay_mov.exists() and overlay_mov.stat().st_size > 500:
        if can_use_vaapi:
            # 1. Hardware-Accelerated VAAPI Compositing (AMD iGPU ~6-7s)
            if has_wm:
                cmd_vaapi = [
                    "ffmpeg", "-y",
                    "-init_hw_device", f"vaapi=va:{vaapi_device}",
                    "-filter_hw_device", "va",
                    "-i", str(input_path),
                    "-itsoffset", f"{t_start:.3f}",
                    "-i", str(overlay_mov),
                    "-i", str(wm_png_path),
                    "-filter_complex", f"[0:v][2:v]overlay=0:0:enable='between(t,0,{t_start:.3f})'[v1];[v1][1:v]overlay=0:0:enable='gte(t,{t_start:.3f})':eof_action=repeat,format=nv12,hwupload[outv]",
                    "-map", "[outv]",
                    "-map", "0:a?",
                    "-c:v", "h264_vaapi",
                    "-qp", "22",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            else:
                cmd_vaapi = [
                    "ffmpeg", "-y",
                    "-init_hw_device", f"vaapi=va:{vaapi_device}",
                    "-filter_hw_device", "va",
                    "-i", str(input_path),
                    "-itsoffset", f"{t_start:.3f}",
                    "-i", str(overlay_mov),
                    "-filter_complex", f"[0:v][1:v]overlay=0:0:enable='between(t,{t_start:.3f},{t_end:.3f})',format=nv12,hwupload[outv]",
                    "-map", "[outv]",
                    "-map", "0:a?",
                    "-c:v", "h264_vaapi",
                    "-qp", "22",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            try:
                res_vaapi = subprocess.run(cmd_vaapi, capture_output=True, text=True, timeout=120)
                if res_vaapi.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                    logger.info(f"Studio CTA overlay applied via VAAPI ({platform} / {chosen_style}): {output_path}")
                    applied = True
                else:
                    logger.warning(f"VAAPI CTA overlay failed: {res_vaapi.stderr[-300:] if res_vaapi.stderr else ''}, falling back to CPU")
            except Exception as e_v:
                logger.warning(f"VAAPI CTA overlay exception: {e_v}, falling back to CPU")

        if not applied:
            # 2. Fast CPU Alpha Overlay Compositing
            if has_wm:
                cmd_cpu = [
                    "ffmpeg", "-y",
                    "-i", str(input_path),
                    "-itsoffset", f"{t_start:.3f}",
                    "-i", str(overlay_mov),
                    "-i", str(wm_png_path),
                    "-filter_complex", f"[0:v][2:v]overlay=0:0:enable='between(t,0,{t_start:.3f})'[v1];[v1][1:v]overlay=0:0:enable='gte(t,{t_start:.3f})':eof_action=repeat[outv]",
                    "-map", "[outv]",
                    "-map", "0:a?",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "22",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            else:
                cmd_cpu = [
                    "ffmpeg", "-y",
                    "-i", str(input_path),
                    "-itsoffset", f"{t_start:.3f}",
                    "-i", str(overlay_mov),
                    "-filter_complex", f"[0:v][1:v]overlay=0:0:enable='between(t,{t_start:.3f},{t_end:.3f})'[outv]",
                    "-map", "[outv]",
                    "-map", "0:a?",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "22",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            try:
                res_cpu = subprocess.run(cmd_cpu, capture_output=True, text=True, timeout=180)
                if res_cpu.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                    logger.info(f"Studio CTA overlay applied via CPU ({platform} / {chosen_style}): {output_path}")
                    applied = True
                else:
                    logger.error(f"CPU CTA overlay failed: {res_cpu.stderr[-300:] if res_cpu.stderr else ''}")
            except Exception as e_c:
                logger.error(f"CPU CTA overlay exception: {e_c}")
    else:
        # 3. Fallback to string filter if MOV build fails
        vf = build_cta_filter(
            video_width=w,
            video_height=h,
            platform=platform,
            handle=handle,
            style=chosen_style,
            position=position,
            start_time=t_start,
            video_duration=duration,
            watermark=watermark
        )
        cmd_fallback = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path)
        ]
        try:
            res_fb = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=180)
            if res_fb.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1024:
                logger.info(f"Fallback CTA filter applied ({platform}): {output_path}")
                applied = True
        except Exception as e_fb:
            logger.error(f"Fallback CTA filter exception: {e_fb}")

    # Cleanup temp watermark dir if any
    if tmp_wm_dir and tmp_wm_dir.exists():
        try:
            import shutil
            shutil.rmtree(tmp_wm_dir, ignore_errors=True)
        except Exception:
            pass

    return applied


# ─── Multiplatform Batch Generator ──────────────────────────────────────────

def generate_multiplatform_cta_overlays(
    input_path: Path,
    output_dir: Path,
    stem_prefix: str = "clip",
    handle: str = "",
    base_style: str = "pill",
    position: str = "lower_center",
    start_time: Optional[float] = None,
    video_width: Optional[int] = None,
    video_height: Optional[int] = None,
    primary_platform: str = "tiktok"
) -> dict:
    """
    Generate 4 platform-specific deliverables with studio animated CTA overlays:
      1. TikTok (Official musical note + + Follow -> cyan Following ✓)
      2. Instagram (Official camera + sunset gradient Follow -> Following ✓)
      3. YouTube Shorts (Official play button + Subscribe -> Subscribed ✓ + Bell)
      4. Facebook (Official circle 'f' + Royal Blue Follow -> Following ✓)
    
    Also generates/links the primary clip_cta.mp4 for default serving.
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logger.error(f"generate_multiplatform_cta_overlays: input_path not found: {input_path}")
        return {}

    # Probe duration and dimensions once
    duration = 30.0
    w = video_width or 1080
    h = video_height or 1920
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "json", str(input_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and res.stdout:
            import json
            info = json.loads(res.stdout)
            if "format" in info and "duration" in info["format"]:
                duration = float(info["format"]["duration"])
            if "streams" in info:
                for s in info["streams"]:
                    if s.get("width") and s.get("height"):
                        w = int(s["width"])
                        h = int(s["height"])
                        break
    except Exception as e:
        logger.debug(f"Probe in generate_multiplatform_cta_overlays: {e}")

    results = {}

    def process_platform(plat: str) -> Tuple[str, Optional[str]]:
        out_file = output_dir / f"{stem_prefix}_{plat}.mp4"
        success = apply_cta_overlay(
            input_path=input_path,
            output_path=out_file,
            platform=plat,
            handle=handle,
            style=base_style,
            position=position,
            start_time=start_time,
            video_width=w,
            video_height=h,
            video_duration=duration
        )
        if success and out_file.exists() and out_file.stat().st_size > 0:
            return plat, str(out_file)
        return plat, None

    # Parallelize rendering across platforms for fast completion
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_plat = {executor.submit(process_platform, p): p for p in SUPPORTED_CTA_PLATFORMS}
        for future in future_to_plat:
            try:
                plat, path = future.result()
                if path:
                    results[plat] = path
                else:
                    logger.warning(f"Failed to generate CTA overlay for {plat}")
            except Exception as pe:
                logger.error(f"Error generating CTA overlay in thread: {pe}")

    # Generate or copy the primary default cta file (e.g. clip_cta.mp4)
    default_cta_file = output_dir / f"{stem_prefix}_cta.mp4"
    primary_key = primary_platform if primary_platform in results else (
        "tiktok" if "tiktok" in results else next(iter(results.keys()), None)
    )
    if primary_key and primary_key in results:
        src = Path(results[primary_key])
        if src.exists():
            try:
                if default_cta_file.exists():
                    default_cta_file.unlink()
                try:
                    os.link(src, default_cta_file)
                except OSError:
                    import shutil
                    shutil.copy2(src, default_cta_file)
            except Exception as copy_err:
                logger.debug(f"Could not link default CTA file: {copy_err}")

    return results
