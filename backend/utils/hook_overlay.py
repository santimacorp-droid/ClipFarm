"""
Studio-grade Full-Color Emoji Hook Banner Overlay Engine (2026 Creative Reels Edition)
Renders high-retention on-screen hook banners with authentic full-color emojis
using Noto Color Emoji (CBDT strike 109) and modern frosted glass capsule styling.

Features:
- Intelligent 2-line auto-wrapping to preserve bold, readable typography on mobile.
- Hormozi / Reels style keyword highlighting (<hl>punch words</hl> in electric gold).
- Category-aware frosted glass theming (Podcasts, Interviews, Vlogs, Business, Tech, etc.).
- Smooth fade-in (0 -> 0.35s) and fade-out (3.80 -> 4.20s) in the top safe area.
"""

import os
import re
import math
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# ─── Font Resolution ─────────────────────────────────────────────────────────

TEXT_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

COLOR_EMOJI_FONT_PATH = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

def _resolve_text_font_path() -> str:
    for p in TEXT_FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return ""

def _resolve_emoji_font_path() -> str:
    if os.path.exists(COLOR_EMOJI_FONT_PATH):
        return COLOR_EMOJI_FONT_PATH
    return ""

# Comprehensive emoji matching regex: supports single emojis, pictographs, symbols,
# dingbats, variation selectors, skin tone modifiers, and ZWJ sequence combinations.
EMOJI_PATTERN = re.compile(
    r'(?:'
    r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]'
    r')(?:[\ufe00-\ufe0f]|[\U0001f3fb-\U0001f3ff]|'
    r'\u200d(?:[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff])(?:[\ufe00-\ufe0f]|[\U0001f3fb-\U0001f3ff])*)*'
)

# ─── Category Theming ─────────────────────────────────────────────────────────

CATEGORY_THEMES: Dict[str, Dict[str, Tuple[int, int, int, int]]] = {
    "podcast": {
        "bg": (15, 18, 26, 235),
        "border": (250, 173, 20, 120),    # Amber border glow
        "accent": (255, 214, 0, 255)      # Vivid gold
    },
    "podcast_highlight": {
        "bg": (15, 18, 26, 235),
        "border": (250, 173, 20, 120),
        "accent": (255, 214, 0, 255)
    },
    "interview": {
        "bg": (16, 20, 28, 235),
        "border": (114, 46, 209, 120),   # Royal violet border
        "accent": (255, 214, 0, 255)
    },
    "vlog": {
        "bg": (18, 18, 24, 230),
        "border": (255, 255, 255, 80),    # Soft pearl white glow
        "accent": (255, 225, 77, 255)     # Warm butter yellow
    },
    "storytelling": {
        "bg": (18, 18, 24, 230),
        "border": (19, 194, 194, 110),   # Cyan glow
        "accent": (255, 214, 0, 255)
    },
    "experience": {
        "bg": (18, 18, 24, 230),
        "border": (250, 140, 22, 110),   # Warm orange
        "accent": (255, 214, 0, 255)
    },
    "business": {
        "bg": (14, 18, 24, 235),
        "border": (82, 196, 26, 110),    # Emerald edge
        "accent": (255, 214, 0, 255)
    },
    "business_insight": {
        "bg": (14, 18, 24, 235),
        "border": (250, 173, 20, 120),   # Gold edge
        "accent": (255, 214, 0, 255)
    },
    "tech_take": {
        "bg": (14, 18, 28, 235),
        "border": (24, 144, 255, 120),   # Electric blue
        "accent": (0, 230, 255, 255)      # Cyan highlight
    },
    "ai_moment": {
        "bg": (14, 18, 28, 235),
        "border": (47, 84, 235, 120),
        "accent": (0, 230, 255, 255)
    },
    "entertainment": {
        "bg": (18, 16, 22, 235),
        "border": (255, 77, 79, 130),    # Crimson edge
        "accent": (255, 214, 0, 255)
    },
    "funny_moment": {
        "bg": (18, 16, 22, 235),
        "border": (250, 140, 22, 120),
        "accent": (255, 214, 0, 255)
    },
    "hot_take": {
        "bg": (20, 16, 22, 235),
        "border": (235, 47, 150, 120),   # Magenta hot
        "accent": (255, 214, 0, 255)
    },
    "knowledge": {
        "bg": (16, 20, 26, 235),
        "border": (250, 173, 20, 110),
        "accent": (255, 214, 0, 255)
    }
}

DEFAULT_THEME = {
    "bg": (16, 20, 28, 230),
    "border": (255, 255, 255, 60),
    "accent": (255, 214, 0, 255)
}


def _resolve_category_colors(category: str) -> Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int], Tuple[int, int, int, int]]:
    cat_key = (category or "general").lower().replace("-", "_").strip()
    theme = CATEGORY_THEMES.get(cat_key, DEFAULT_THEME)
    return theme["bg"], theme["border"], theme["accent"]


# ─── Tokenization & Layout Helper ───────────────────────────────────────────

def _tokenize_hook_units(clean_text: str) -> List[Tuple[str, str, bool]]:
    """
    Parses text with optional <hl>...</hl> tags into atomic display units:
    Returns list of (kind, value, is_highlighted) where kind is 'text' (single word) or 'emoji'.
    """
    parts = re.split(r'(</?hl>)', clean_text, flags=re.IGNORECASE)
    units: List[Tuple[str, str, bool]] = []
    is_hl = False

    for p in parts:
        if not p:
            continue
        low = p.lower()
        if low == '<hl>':
            is_hl = True
        elif low == '</hl>':
            is_hl = False
        else:
            last_idx = 0
            for m in EMOJI_PATTERN.finditer(p):
                if m.start() > last_idx:
                    sub = p[last_idx:m.start()]
                    for word in sub.split():
                        units.append(('text', word, is_hl))
                units.append(('emoji', m.group(0), is_hl))
                last_idx = m.end()
            if last_idx < len(p):
                sub = p[last_idx:]
                for word in sub.split():
                    units.append(('text', word, is_hl))

    return units


def _measure_units_width(
    units: List[Tuple[str, str, bool]],
    draw: ImageDraw.Draw,
    font: ImageFont.ImageFont,
    target_em_h: int,
    space_w: int,
    res_scale: float
) -> int:
    """Calculates the total horizontal rendering width for a line of units."""
    if not units:
        return 0
    total_w = 0
    spacing = int(6 * res_scale)
    for i, (kind, val, _) in enumerate(units):
        if kind == "text":
            bb = draw.textbbox((0, 0), val, font=font)
            total_w += (bb[2] - bb[0])
        else:
            total_w += target_em_h + spacing

        if i < len(units) - 1:
            total_w += space_w
    return total_w


def _find_best_line_split(
    units: List[Tuple[str, str, bool]],
    draw: ImageDraw.Draw,
    font: ImageFont.ImageFont,
    target_em_h: int,
    space_w: int,
    res_scale: float
) -> Tuple[List[Tuple[str, str, bool]], List[Tuple[str, str, bool]]]:
    """
    Finds the optimal split point between word units to balance the widths of Line 1 and Line 2.
    """
    if len(units) <= 1:
        return units, []

    best_diff = float('inf')
    best_split = len(units) // 2

    for k in range(1, len(units)):
        l1 = units[:k]
        l2 = units[k:]
        w1 = _measure_units_width(l1, draw, font, target_em_h, space_w, res_scale)
        w2 = _measure_units_width(l2, draw, font, target_em_h, space_w, res_scale)
        diff = abs(w1 - w2)
        if diff < best_diff:
            best_diff = diff
            best_split = k

    return units[:best_split], units[best_split:]


# ─── Banner Image Rendering (Pillow) ─────────────────────────────────────────

def render_color_emoji_hook_banner(
    text: str,
    video_width: int = 1080,
    video_height: int = 1920,
    max_width_ratio: float = 0.88,
    output_path: Optional[Path] = None,
    bg_color: Optional[Tuple[int, int, int, int]] = None,
    border_color: Optional[Tuple[int, int, int, int]] = None,
    text_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    accent_color: Optional[Tuple[int, int, int, int]] = None,
    category: str = "general"
) -> Image.Image:
    """
    Renders a studio-grade frosted glass stadium capsule containing clean bold text,
    optional highlighted keywords (<hl>), and authentic full-color emojis from Noto Color Emoji.

    Automatically wraps into 2 balanced lines when text is long, keeping typography bold
    and readable (32px-44px) rather than squishing into tiny unreadable font sizes.
    """
    clean_text = str(text or "").strip()
    if (clean_text.startswith('"') and clean_text.endswith('"')) or (clean_text.startswith("'") and clean_text.endswith("'")):
        clean_text = clean_text[1:-1].strip()

    if not clean_text:
        clean_text = "MUST WATCH 🔥"

    # Resolve category-specific theming if colors not explicitly overridden
    cat_bg, cat_border, cat_accent = _resolve_category_colors(category)
    if bg_color is None:
        bg_color = cat_bg
    if border_color is None:
        border_color = cat_border
    if accent_color is None:
        accent_color = cat_accent

    text_font_path = _resolve_text_font_path()
    emoji_font_path = _resolve_emoji_font_path()

    emoji_font = None
    if emoji_font_path:
        try:
            # NotoColorEmoji uses fixed strike bitmap size 109
            emoji_font = ImageFont.truetype(emoji_font_path, 109)
        except Exception as ef_err:
            logger.debug(f"Could not load NotoColorEmoji: {ef_err}")

    # Scale factor relative to standard 1080p
    res_scale = max(0.5, min(2.0, video_width / 1080.0))
    shadow_margin = int(18 * res_scale)
    max_w = int(video_width * max_width_ratio)
    target_max_pill_w = max(200, max_w - shadow_margin * 2)

    units = _tokenize_hook_units(clean_text)
    if not units:
        units = [("text", "MUST", False), ("text", "WATCH", False), ("emoji", "🔥", False)]

    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)

    # Typography sizing limits
    base_max_fs = int(44 * res_scale)
    base_min_fs = int(28 * res_scale)

    # 1. First test: can all units fit comfortably on a SINGLE line at bold size (>= 36px)?
    single_line_font = None
    single_line_fs = base_min_fs
    single_line_fits = False

    for fs in range(base_max_fs, int(35 * res_scale), -2):
        font = ImageFont.truetype(text_font_path, fs) if text_font_path else ImageFont.load_default()
        pad_x = int(fs * 0.85)
        target_em_h = int(fs * 1.16)
        space_w = dummy_draw.textbbox((0, 0), " ", font=font)[2]
        line_w = _measure_units_width(units, dummy_draw, font, target_em_h, space_w, res_scale)
        if line_w + pad_x * 2 <= target_max_pill_w:
            single_line_fits = True
            single_line_fs = fs
            single_line_font = font
            break

    # Decide layout: 1 line if fits comfortably, otherwise 2 lines
    if single_line_fits and len(units) <= 6:
        lines = [units]
        chosen_fs = single_line_fs
        chosen_font = single_line_font
    else:
        # Wrap into 2 balanced lines
        temp_font = ImageFont.truetype(text_font_path, int(36 * res_scale)) if text_font_path else ImageFont.load_default()
        temp_em_h = int(36 * res_scale * 1.16)
        temp_space_w = dummy_draw.textbbox((0, 0), " ", font=temp_font)[2]
        l1, l2 = _find_best_line_split(units, dummy_draw, temp_font, temp_em_h, temp_space_w, res_scale)
        lines = [l1, l2] if l2 else [l1]

        # Find best font size for 2-line layout
        chosen_fs = base_min_fs
        chosen_font = None

        for fs in range(base_max_fs, base_min_fs - 1, -2):
            font = ImageFont.truetype(text_font_path, fs) if text_font_path else ImageFont.load_default()
            pad_x = int(fs * 0.85)
            target_em_h = int(fs * 1.16)
            space_w = dummy_draw.textbbox((0, 0), " ", font=font)[2]
            max_lw = max(_measure_units_width(line, dummy_draw, font, target_em_h, space_w, res_scale) for line in lines)
            if max_lw + pad_x * 2 <= target_max_pill_w:
                chosen_fs = fs
                chosen_font = font
                break
            chosen_fs = fs
            chosen_font = font

        # Proportional downscale if still overflowing target width
        pad_x = int(chosen_fs * 0.85)
        target_em_h = int(chosen_fs * 1.16)
        space_w = dummy_draw.textbbox((0, 0), " ", font=chosen_font)[2]
        max_lw = max(_measure_units_width(line, dummy_draw, chosen_font, target_em_h, space_w, res_scale) for line in lines)
        if max_lw + pad_x * 2 > target_max_pill_w:
            downscale = target_max_pill_w / float(max(1, max_lw + pad_x * 2))
            chosen_fs = max(10, int(chosen_fs * downscale))
            chosen_font = ImageFont.truetype(text_font_path, chosen_fs) if text_font_path else ImageFont.load_default()

    # Layout dimensions
    pad_x = int(chosen_fs * 0.88)
    pad_y = int(chosen_fs * 0.46)
    target_em_h = int(chosen_fs * 1.16)
    space_w = dummy_draw.textbbox((0, 0), " ", font=chosen_font)[2]
    spacing = int(6 * res_scale)
    line_spacing = int(chosen_fs * 0.28) if len(lines) > 1 else 0

    # Measure each line's width
    line_widths = [_measure_units_width(l, dummy_draw, chosen_font, target_em_h, space_w, res_scale) for l in lines]
    max_line_w = max(line_widths) if line_widths else 200

    pill_w = max_line_w + pad_x * 2
    pill_h = (target_em_h * len(lines)) + line_spacing * (len(lines) - 1) + pad_y * 2
    radius = min(pill_h // 2, int(26 * res_scale)) if len(lines) > 1 else (pill_h // 2)

    canvas_w = pill_w + shadow_margin * 2
    canvas_h = pill_h + shadow_margin * 2

    banner = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)

    # 1. Soft Drop Shadow
    shadow_offset_y = int(5 * res_scale)
    shadow_box = [
        (shadow_margin + 2, shadow_margin + shadow_offset_y),
        (shadow_margin + pill_w + 2, shadow_margin + pill_h + shadow_offset_y)
    ]
    draw.rounded_rectangle(shadow_box, radius=radius, fill=(0, 0, 0, 115))
    banner = banner.filter(ImageFilter.GaussianBlur(radius=int(7 * res_scale)))
    draw = ImageDraw.Draw(banner)

    # 2. Frosted Pill Body
    pill_box = [
        (shadow_margin, shadow_margin),
        (shadow_margin + pill_w, shadow_margin + pill_h)
    ]
    draw.rounded_rectangle(pill_box, radius=radius, fill=bg_color, outline=border_color, width=max(1, int(2 * res_scale)))

    # 3. Draw Lines & Content
    for line_idx, line in enumerate(lines):
        lw = line_widths[line_idx]
        cur_x = shadow_margin + (pill_w - lw) // 2
        line_center_y = shadow_margin + pad_y + (line_idx * (target_em_h + line_spacing)) + target_em_h // 2

        for i, (kind, val, is_hl) in enumerate(line):
            fill_color = accent_color if is_hl else text_color

            if kind == "text":
                bb = dummy_draw.textbbox((0, 0), val, font=chosen_font)
                tw = bb[2] - bb[0]
                th = bb[3] - bb[1]
                draw.text(
                    (cur_x - bb[0], line_center_y - th // 2 - int(2 * res_scale)),
                    val,
                    font=chosen_font,
                    fill=fill_color
                )
                cur_x += tw
            elif kind == "emoji":
                # Emoji rendering with strike size 109 and LANCZOS downscale
                rendered_em = None
                if emoji_font:
                    try:
                        raw_em = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
                        raw_draw = ImageDraw.Draw(raw_em)
                        raw_draw.text((8, 8), val, font=emoji_font, embedded_color=True)
                        em_bbox = raw_em.getbbox()
                        if em_bbox:
                            cropped = raw_em.crop(em_bbox)
                            cw, ch = cropped.size
                            scale = target_em_h / float(ch)
                            ew = max(8, int(cw * scale))
                            resized = cropped.resize((ew, target_em_h), Image.Resampling.LANCZOS)
                            rendered_em = (resized, ew)
                    except Exception as ex:
                        logger.debug(f"Failed to render emoji {val}: {ex}")

                if rendered_em:
                    img_em, ew = rendered_em
                    ey = line_center_y - img_em.height // 2
                    banner.paste(img_em, (cur_x, ey), img_em)
                    cur_x += ew + spacing
                else:
                    # Text glyph fallback
                    bb = dummy_draw.textbbox((0, 0), val, font=chosen_font)
                    tw = bb[2] - bb[0]
                    th = bb[3] - bb[1]
                    draw.text(
                        (cur_x - bb[0], line_center_y - th // 2 - int(2 * res_scale)),
                        val,
                        font=chosen_font,
                        fill=fill_color
                    )
                    cur_x += tw

            if i < len(line) - 1:
                cur_x += space_w

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        banner.save(out_p, "PNG")

    return banner


# ─── 2026 Narrative Story / Meme Top Black Header Renderer ──────────────────

def render_black_header_hook(
    text: str,
    canvas_w: int = 1080,
    header_h: int = 520,
    output_path: Optional[Path] = None,
    text_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    accent_color: Tuple[int, int, int, int] = (255, 214, 0, 255),
    bg_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    padding_x: int = 70,
    padding_y: int = 40,
) -> Image.Image:
    """
    Renders an authentic 2026 Meme / Narrative Story Reel top header banner with
    solid black background, centered multi-line typography (supporting 1 to 6 lines),
    and optional subtle emojis.
    
    Used for story reels like:
    - "The day Robin Williams made Koko laugh, a gorilla who had been mourning the death of her son for 6 months"
    - "When super nanny realizes this Little boy wasn't misbehaving he just missed his mom🥺"
    - "It hits different when you're the loser the constant disappointment in yourself..."
    - "When Miley cyrus stopped singing to record the fans fighting"
    """
    clean_text = str(text or "").strip()
    if (clean_text.startswith('"') and clean_text.endswith('"')) or (clean_text.startswith("'") and clean_text.endswith("'")):
        clean_text = clean_text[1:-1].strip()

    if not clean_text:
        clean_text = "Must Watch"

    text_font_path = _resolve_text_font_path()
    emoji_font_path = _resolve_emoji_font_path()

    emoji_font = None
    if emoji_font_path:
        try:
            emoji_font = ImageFont.truetype(emoji_font_path, 109)
        except Exception:
            emoji_font = None

    units = _tokenize_hook_units(clean_text)
    if not units:
        units = [("text", clean_text, False)]

    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)

    max_text_w = max(200, canvas_w - (padding_x * 2))
    max_text_h = max(100, header_h - (padding_y * 2))

    # Determine optimal font size by wrapping units
    chosen_fs = 48
    chosen_lines: List[List[Tuple[str, str, bool]]] = []
    chosen_line_h = int(chosen_fs * 1.32)

    for fs in range(54, 24, -2):
        if text_font_path:
            font = ImageFont.truetype(text_font_path, fs)
        else:
            font = ImageFont.load_default()

        space_w = dummy_draw.textlength(" ", font=font)
        em_h = int(fs * 1.15)

        # Measure each unit
        unit_widths = []
        for kind, val, _ in units:
            if kind == "emoji":
                unit_widths.append(em_h + 4)
            else:
                unit_widths.append(dummy_draw.textlength(val, font=font))

        # Greedy line wrapping
        candidate_lines: List[List[Tuple[str, str, bool]]] = []
        cur_line: List[Tuple[str, str, bool]] = []
        cur_line_w = 0.0

        for idx, unit in enumerate(units):
            uw = unit_widths[idx]
            needed_w = uw if not cur_line else (cur_line_w + space_w + uw)
            if needed_w <= max_text_w:
                cur_line.append(unit)
                cur_line_w = needed_w
            else:
                if cur_line:
                    candidate_lines.append(cur_line)
                cur_line = [unit]
                cur_line_w = uw

        if cur_line:
            candidate_lines.append(cur_line)

        line_h = int(fs * 1.32)
        total_h = len(candidate_lines) * line_h
        if total_h <= max_text_h:
            chosen_fs = fs
            chosen_lines = candidate_lines
            chosen_line_h = line_h
            break

    # If even smallest font size didn't trigger break, take the last candidate
    if not chosen_lines:
        chosen_lines = [units]
        chosen_fs = 26
        chosen_line_h = int(chosen_fs * 1.32)

    # Load chosen font
    if text_font_path:
        font = ImageFont.truetype(text_font_path, chosen_fs)
    else:
        font = ImageFont.load_default()
    space_w = dummy_draw.textlength(" ", font=font)
    em_h = int(chosen_fs * 1.15)

    # Create solid header image
    header_img = Image.new("RGBA", (canvas_w, header_h), bg_color)
    draw = ImageDraw.Draw(header_img)

    total_text_h = len(chosen_lines) * chosen_line_h
    start_y = max(padding_y // 2, (header_h - total_text_h) // 2)

    for line_idx, line in enumerate(chosen_lines):
        # Measure line width
        line_w = 0.0
        for i, (kind, val, _) in enumerate(line):
            if kind == "emoji":
                line_w += em_h + 4
            else:
                line_w += dummy_draw.textlength(val, font=font)
            if i < len(line) - 1:
                line_w += space_w

        cur_x = (canvas_w - line_w) // 2
        line_y = start_y + line_idx * chosen_line_h

        for i, (kind, val, is_hl) in enumerate(line):
            fill_col = accent_color if is_hl else text_color

            if kind == "emoji":
                em_img = None
                if emoji_font:
                    try:
                        em_img = _render_color_emoji_strike(val, emoji_font, em_h)
                    except Exception:
                        em_img = None

                if em_img:
                    ey = int(line_y + (chosen_line_h - em_h) // 2)
                    header_img.paste(em_img, (int(cur_x), ey), em_img)
                    cur_x += em_h + 4
                else:
                    draw.text((cur_x, line_y), val, font=font, fill=fill_col)
                    cur_x += dummy_draw.textlength(val, font=font)
            else:
                # Crisp white text with subtle shadow
                draw.text((cur_x + 1, line_y + 1), val, font=font, fill=(0, 0, 0, 180))
                draw.text((cur_x, line_y), val, font=font, fill=fill_col)
                cur_x += dummy_draw.textlength(val, font=font)

            if i < len(line) - 1:
                cur_x += space_w

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        header_img.save(out_p, "PNG")

    return header_img


# ─── Video Hook Compositor (FFmpeg) ─────────────────────────────────────────

def build_hook_overlay_filter(
    duration: float = 4.2,
    fade_in: float = 0.35,
    fade_out: float = 0.40,
    y_offset: int = 180,
    input_label: str = "0:v",
    hook_input_idx: int = 1,
    output_label: str = "v_hook"
) -> str:
    """
    Returns an FFmpeg filter_complex fragment that overlays the hook banner PNG
    with smooth fade-in and fade-out at the top safe-zone.
    """
    out_st = max(0.1, duration - fade_out)
    return (
        f"[{hook_input_idx}:v]format=rgba,"
        f"fade=t=in:st=0:d={fade_in:.2f}:alpha=1,"
        f"fade=t=out:st={out_st:.2f}:d={fade_out:.2f}:alpha=1[hook_faded];"
        f"[{input_label}][hook_faded]overlay=x=(W-w)/2:y={y_offset}:shortest=1:enable='between(t,0,{duration:.2f})'[{output_label}]"
    )


def build_black_header_overlay_filter(
    header_input_idx: int = 1,
    input_label: str = "0:v",
    output_label: str = "v_header"
) -> str:
    """
    Returns an FFmpeg filter_complex fragment that overlays the persistent top black header banner
    across the entire duration of the clip.
    """
    return (
        f"[{header_input_idx}:v]format=rgba[hdr_top];"
        f"[{input_label}][hdr_top]overlay=0:0:shortest=1[{output_label}]"
    )


def apply_hook_overlay(
    input_path: Path,
    output_path: Path,
    hook_text: str,
    duration: float = 4.2,
    y_offset: Optional[int] = None,
    video_width: Optional[int] = None,
    video_height: Optional[int] = None,
    category: str = "general"
) -> bool:
    """
    Burns a full-color emoji hook banner into an existing video clip
    in the opening `duration` seconds (default 4.2s).
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logger.error(f"apply_hook_overlay: input not found at {input_path}")
        return False

    if not hook_text or not hook_text.strip():
        logger.warning("apply_hook_overlay: empty hook_text, skipping overlay")
        shutil.copy2(input_path, output_path)
        return True

    # Probe resolution if not given
    if not video_width or not video_height:
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                str(input_path)
            ]
            res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            w_str, h_str = res.stdout.strip().split(",")
            video_width = int(w_str)
            video_height = int(h_str)
        except Exception as probe_err:
            logger.debug(f"Probe failed ({probe_err}), falling back to 1080x1920")
            video_width = 1080
            video_height = 1920

    if y_offset is None:
        y_offset = int(video_height * 0.09)

    banner_png = output_path.parent / f"{output_path.stem}_hook_banner.png"
    try:
        render_color_emoji_hook_banner(
            text=hook_text,
            video_width=video_width,
            video_height=video_height,
            output_path=banner_png,
            category=category
        )
    except Exception as ren_err:
        logger.error(f"Failed to render hook banner PNG: {ren_err}")
        shutil.copy2(input_path, output_path)
        return False

    filt = build_hook_overlay_filter(
        duration=duration,
        fade_in=0.35,
        fade_out=0.40,
        y_offset=y_offset,
        input_label="0:v",
        hook_input_idx=1,
        output_label="v_hook"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-loop", "1", "-i", str(banner_png),
        "-filter_complex", filt,
        "-map", "[v_hook]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "copy",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        if banner_png.exists():
            banner_png.unlink(missing_ok=True)
        return True
    except subprocess.CalledProcessError as f_err:
        logger.error(f"FFmpeg hook overlay failed: {f_err.stderr.decode('utf-8', errors='ignore')}")
        shutil.copy2(input_path, output_path)
        return False
