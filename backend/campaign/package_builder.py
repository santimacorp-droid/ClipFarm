"""
Assemble per-clip output packages: compliance checklist, platform post guide.
"""
from typing import List, Optional
from ..schemas.campaign import ComplianceItem

def build_compliance_checklist(
    duration_sec: float,
    duration_min: float,
    duration_max: float,
    logo_applied: bool,
    styled_captions_off: bool,
    min_days_live: int,
    min_engagement_rate: float,
    ftc_required: bool,
    logo_required: bool = False
) -> List[dict]:
    """Build the compliance checklist for a single clip."""
    items = []
    
    # Duration check
    in_range = duration_min <= duration_sec <= duration_max
    items.append({
        "item":   f"Clip is {int(duration_min)}–{int(duration_max)} seconds",
        "status": "pass" if in_range else "fail",
        "value":  f"{duration_sec:.1f}s"
    })
    
    # Logo check
    if logo_required:
        items.append({
            "item":   "Brand logo visible on clip",
            "status": "pass" if logo_applied else "fail"
        })
    else:
        items.append({
            "item":   "Brand logo / Watermark",
            "status": "pass",
            "value":  "Not required by brand"
        })
    
    # Styled captions
    if not styled_captions_off:
        items.append({
            "item":   "No styled captions (native subtitles only)",
            "status": "manual",
            "value":  "Verify styled captions are off before posting"
        })
    
    # Manual checks (user must verify after posting)
    items.append({"item": "Only authorized people appear in clip", "status": "manual"})
    items.append({"item": "No external footage used",             "status": "manual"})
    
    # Post-publishing checks (pending until user confirms)
    items.append({"item": f"Post stays live for {min_days_live}+ days", "status": "pending"})
    items.append({"item": "Likes are visible on post",                   "status": "pending"})
    items.append({"item": f"Engagement rate ≥ {min_engagement_rate*100:.2f}%", "status": "pending"})
    
    if ftc_required:
        items.append({"item": "FTC compliance disclosed in post", "status": "pending"})
    
    return items


def build_platform_post_guide(
    chosen_caption: str,
    platform_tags:  dict,
    moment_name:    str,
    transcript_text: str = "",
    brand_name:     str = "Brand",
    llm_guide:      Optional[dict] = None
) -> dict:
    """Build copy-paste ready post guide per platform (TikTok, Instagram, YouTube Shorts, Facebook)."""
    if llm_guide and isinstance(llm_guide, dict):
        return llm_guide

    from .copy_generator import _heuristic_fallback_copy
    copy_res = _heuristic_fallback_copy(
        moment_name=moment_name,
        transcript_text=transcript_text,
        brand_name=brand_name,
        platform_tags=platform_tags,
        caption_options=[chosen_caption] if chosen_caption else None
    )

    # Return platform post guide dictionary
    return {
        "tiktok": copy_res.get("tiktok", {}),
        "instagram": copy_res.get("instagram", {}),
        "youtube_shorts": copy_res.get("youtube_shorts", {}),
        "facebook": copy_res.get("facebook", {})
    }

