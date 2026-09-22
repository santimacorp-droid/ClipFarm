"""
LLM-powered campaign brief parser.
Takes raw pasted brief text → returns CampaignSchema dict.
"""
import json
import logging
import re
from typing import Optional
from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

PARSE_PROMPT = """You are a campaign brief parser for a short-form video clipping platform.

Extract all structured information from the campaign brief below into a JSON object matching this exact schema.
If a field is not mentioned in the brief, use null or the default shown.
Be precise — do not infer requirements not explicitly stated. Do not add restrictions not in the brief.

Output schema:
{
  "brand_name": "string — brand/company name",
  "campaign_name": "string — full campaign name",
  "source_video_url": "string | null — URL to source video",
  "logo_url": "string | null — URL to brand logo file",
  "clip_duration": {
    "min_seconds": "number — minimum clip length in seconds (default 15). NEVER use single digits like 1 or 2. If brief says 'at least 10 seconds', use 10.",
    "max_seconds": "number — MAXIMUM CEILING in seconds — clips should end when thought is complete, not at this exact time. If brief says '15-40 seconds', set max to 40. If no max given, use 90 (or 180). NEVER confuse audience tiers like 'Tier 1-2' or clip counts like '1-2 clips' with duration seconds!",
    "is_moment_based": "boolean — true if no specific seconds range is mandated in the brief guidelines and duration should be determined by natural spoken thoughts/moments (default true when not specified)"
  },
  "priority_moments": [
    {
      "name": "string — short name for this moment (themes, quotes, or scenes). Do NOT include editing rules or instructions like 'lead with strongest moment', 'avoid long intros', 'experiment with hooks', or 'post to tiktok'",
      "description": "string | null — description of what happens",
      "start_line": "string | null — exact or near-exact quote where this moment starts"
    }
  ],
  "caption_options": ["string", ...],
  "platform_tags": {
    "tiktok": ["@handle", ...],
    "instagram": ["@handle", ...],
    "youtube_shorts": ["@handle", ...]
  },
  "restrictions": {
    "subtitles": "native_preferred | styled_burned | clean_srt_only | optional | none | required",
    "caption_style": "hormozi_yellow | neon_green | neon_cyan | minimal_box | none",
    "styled_captions": boolean,
    "background_music": "allowed_low | not_recommended | forbidden",
    "logo_required": boolean,
    "logo_position": "top_right | top_left | bottom_right | bottom_left",
    "logo_scale_percent": 0.12,
    "output_format": "blur_pad | crop_center | original  (default: blur_pad)",
    "other_people_allowed": boolean,
    "external_footage_allowed": boolean,
    "filters_allowed": boolean,
    "edit_mode": "moment_extraction (default) | full_video_edit. Use 'full_video_edit' when: the brief says to 'use this clip', 'edit this segment', 'post this video' (whole video is the content), only 1 priority moment covers essentially the full video length, or the video is clearly a short standalone clip, NOT a long interview/podcast to extract from. Use 'moment_extraction' for long source videos where specific moments are listed.",
    "outro_style": "none (default) | follow_handle | check_bio | custom_text",
    "outro_handle": "social handle for follow_handle outro (e.g. '@frida')",
    "outro_text": "text for custom_text outro"
  },
  "compliance": {
    "min_days_live": number,
    "min_engagement_rate": number,
    "likes_must_be_visible": boolean,
    "tier1_2_audience_required": boolean,
    "ftc_compliant": boolean
  }
}

Return ONLY the valid JSON object. No explanation, no markdown code block wrapper.

Brief to parse:
"""

def extract_clip_duration(raw_brief: str) -> dict:
    """
    Extract clip duration requirements conditionally.
    If no explicit seconds or duration range is specified in the guidelines,
    it defaults to moment-based (15s – 90s).
    Sanity checks prevent absurd durations (e.g. 1s - 2s from 'Tier 1-2').
    """
    # 1. Check for explicit range with required time unit:
    # e.g. "15-40s", "30 to 60 seconds", "15 - 60 sec", "1 - 2 minutes", "1-2 mins"
    range_sec_match = re.search(
        r'(?<![A-Za-z0-9])(\d+)\s*(?:-|–|to)\s*(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes)\b',
        raw_brief,
        re.IGNORECASE
    )
    
    # 2. Check for explicit duration keywords with numbers:
    # e.g. "clip duration: 15-40", "duration: 30 - 60", "length: 20 to 60"
    keyword_range_match = None
    if not range_sec_match:
        keyword_range_match = re.search(
            r'(?:clip\s*duration|target\s*duration|video\s*length|duration|length)\s*[:\-]?\s*(\d+)\s*(?:-|–|to)\s*(\d+)\b',
            raw_brief,
            re.IGNORECASE
        )

    # 3. Check for single bound with time unit:
    # e.g. "at least 10 seconds", "minimum 15s", "under 60s", "max 90 seconds"
    at_least_match = re.search(
        r'(?:at\s*least|minimum|min|no\s*less\s*than)\s*[:\-]?\s*(\d+)\s*(s|sec|secs|second|seconds|min|mins|minutes)\b',
        raw_brief,
        re.IGNORECASE
    )
    under_match = re.search(
        r'(?:under|maximum|max|no\s*more\s*than|up\s*to)\s*[:\-]?\s*(\d+)\s*(s|sec|secs|second|seconds|min|mins|minutes)\b',
        raw_brief,
        re.IGNORECASE
    )

    min_sec = 15.0
    max_sec = 90.0
    is_moment_based = True

    if range_sec_match:
        n1 = float(range_sec_match.group(1))
        n2 = float(range_sec_match.group(2))
        unit = range_sec_match.group(3).lower()
        if unit.startswith('m'):
            n1 *= 60.0
            n2 *= 60.0
        # Sanity check: minimum clip cannot be under 5s, max under 10s
        if n2 >= 10.0 and n2 > n1:
            min_sec = max(5.0, n1)
            max_sec = n2
            is_moment_based = False
    elif keyword_range_match:
        n1 = float(keyword_range_match.group(1))
        n2 = float(keyword_range_match.group(2))
        if n2 >= 10.0 and n2 > n1:
            min_sec = max(5.0, n1)
            max_sec = n2
            is_moment_based = False

    if at_least_match:
        n = float(at_least_match.group(1))
        unit = at_least_match.group(2).lower()
        if unit.startswith('m'):
            n *= 60.0
        if 5.0 <= n <= 180.0:
            min_sec = n
            if is_moment_based:
                max_sec = max(90.0, min_sec + 45.0)

    if under_match:
        n = float(under_match.group(1))
        unit = under_match.group(2).lower()
        if unit.startswith('m'):
            n *= 60.0
        if n >= 15.0:
            max_sec = n
            is_moment_based = False

    # Universal Safety Clamp:
    if max_sec < 10.0:
        min_sec = 15.0
        max_sec = 90.0
        is_moment_based = True
    elif min_sec >= max_sec:
        min_sec = max(10.0, min_sec)
        max_sec = min_sec + 45.0

    return {
        "min_seconds": min_sec,
        "max_seconds": max_sec,
        "is_moment_based": is_moment_based
    }


def fast_parse_brief_heuristic(raw_brief: str) -> dict:
    """
    Ultra-fast heuristic extraction (<5ms) using regex and pattern rules.
    Extracts brand, campaign title, links, duration constraints, moments, tags, and compliance.
    """
    lines = [l.strip() for l in raw_brief.splitlines() if l.strip()]
    
    brand_name = "Unknown Brand"
    campaign_name = "Campaign Brief"
    
    # 1. Brand & Campaign Title detection
    brand_match = re.search(r'(?:brand|company|client)\s*(?:name)?\s*[:\-]\s*([^\n\r,;]+)', raw_brief, re.IGNORECASE)
    if brand_match:
        brand_name = brand_match.group(1).strip()
    
    camp_match = re.search(r'(?:campaign|project|title)\s*(?:name)?\s*[:\-]\s*([^\n\r,;]+)', raw_brief, re.IGNORECASE)
    if camp_match:
        campaign_name = camp_match.group(1).strip()
    elif lines:
        first_line = lines[0].lstrip('#').strip()
        if len(first_line) < 80 and not first_line.lower().startswith(("what to do", "guidelines", "brief")):
            campaign_name = first_line
            if brand_name == "Unknown Brand" and " - " in first_line:
                brand_name = first_line.split(" - ")[0].strip()

    # Mentions & Tags
    tags = re.findall(r'#(\w+)', raw_brief)
    mentions = re.findall(r'@([A-Za-z0-9_.]+)', raw_brief)
    formatted_tags = [f"#{t}" for t in set(tags)]
    formatted_mentions = [f"@{m}" for m in set(mentions)]
    all_platform_tags = formatted_mentions + formatted_tags

    # Infer brand name if still Unknown
    if brand_name == "Unknown Brand":
        if mentions:
            brand_name = mentions[0].title()
        else:
            brand_ref = re.search(r'(?:reference to|add the|folder for)\s+([A-Z][a-z0-9]+)', raw_brief)
            if brand_ref:
                brand_name = brand_ref.group(1).strip()

    if campaign_name in ("Campaign Brief", "WHAT TO DO") and brand_name != "Unknown Brand":
        campaign_name = f"{brand_name} Campaign"

    # 2. Video URL detection
    source_video_url = None
    url_matches = re.findall(r'https?://[^\s)\]"\'>]+', raw_brief)
    for u in url_matches:
        u_lower = u.lower()
        if any(kw in u_lower for kw in ["drive.google", "youtube.com", "youtu.be", "dropbox", "vimeo", ".mp4", ".mov", "bilibili"]):
            source_video_url = u
            break
    if not source_video_url and url_matches:
        source_video_url = url_matches[0]

    # 3. Logo URL detection
    logo_url = None
    for u in url_matches:
        if any(kw in u.lower() for kw in ["logo", "watermark", "asset", ".png", ".svg", ".jpg"]):
            logo_url = u
            break

    # 4. Duration detection (conditional and robust)
    clip_duration = extract_clip_duration(raw_brief)

    # 5. Section-aware extraction for Moments and Captions
    priority_moments = []
    caption_options = []
    
    in_moments_section = False
    in_captions_section = False

    for line in lines:
        l_lower = line.lower()
        # Section header triggers
        if any(kw in l_lower for kw in ["prioritize moments", "moments to prioritize", "priority moments", "moments to clip", "scenes to cut"]):
            in_moments_section = True
            in_captions_section = False
            continue
        elif any(kw in l_lower for kw in ["caption guidelines", "caption options", "captions to choose", "suggested captions"]):
            in_captions_section = True
            in_moments_section = False
            continue
        elif line.isupper() or any(line.startswith(h) for h in ["TAGGING", "LOGO", "EDITING", "REQUIREMENTS", "NOT ALLOWED", "Content folder", "⚠️"]):
            in_moments_section = False
            in_captions_section = False

        # Extract moments
        if in_moments_section and re.match(r'^[✔✓\-*•\d+\.]', line):
            cleaned = re.sub(r'^[✔✓\-*•\d+\.]\s*', '', line).strip()
            if cleaned and not cleaned.lower().startswith('prioritize'):
                c_lower = cleaned.lower()
                # Filter out editing instructions and guidelines
                if any(c_lower.startswith(p) for p in ['lead with', 'avoid', 'experiment with', 'post to', 'do not', 'don\'t', 'make sure', 'rotate your', 'choose ones', 'tier']):
                    continue
                if any(kw in c_lower for kw in ['avoid long intros', 'don\'t all clip', 'post to tiktok', 'post to instagram', 'tier 1']):
                    continue

                # Find quotes with ascii or unicode curly quotes
                quotes = re.findall(r'["“\'\u2018\u201c]([^"”\'\u2019\u201d]{4,})["”\'\u2019\u201d]', cleaned)
                start_line = quotes[0] if quotes else ""
                
                # Derive clean moment name (before em-dash, dash, or colon)
                name = re.split(r'\s*[—–\-:]\s*', cleaned)[0][:55].strip()
                if len(name) >= 3:
                    priority_moments.append({
                        "name": name,
                        "description": cleaned,
                        "start_line": start_line
                    })
        elif not in_moments_section:
            # Fallback inline moment detection
            m_match = re.match(r'^(?:[-*•✔✓]|\bscene\b|\bmoment\b|\bhook\b)\s*[:\-]?\s*(.+)', line, re.IGNORECASE)
            if m_match and any(kw in l_lower for kw in ["starts", "quote", "moment:"]):
                cleaned = m_match.group(1).strip()
                c_lower = cleaned.lower()
                if not any(c_lower.startswith(p) for p in ['lead with', 'avoid', 'experiment with', 'post to', 'do not', 'don\'t', 'tier']):
                    quotes = re.findall(r'["“\'\u2018\u201c]([^"”\'\u2019\u201d]{4,})["”\'\u2019\u201d]', cleaned)
                    name = re.split(r'\s*[—–\-:]\s*', cleaned)[0][:55].strip()
                    priority_moments.append({
                        "name": name,
                        "description": cleaned,
                        "start_line": quotes[0] if quotes else ""
                    })

        # Extract captions
        if in_captions_section and re.match(r'^[✔✓\-*•]', line):
            cleaned = re.sub(r'^[✔✓\-*•]\s*', '', line).strip()
            if len(cleaned) > 5:
                caption_options.append(cleaned)
        elif re.search(r'^(?:caption|hook|title\s*option)\s*[:\-]\s*(.+)', line, re.IGNORECASE):
            c_text = re.sub(r'^(?:caption|hook|title\s*option)\s*[:\-]\s*', '', line, flags=re.IGNORECASE).strip(' "\'“')
            if c_text:
                caption_options.append(c_text)

    # 6. Compliance & Restrictions
    styled_captions = False
    if "styled caption" in raw_brief.lower() or "hormozi" in raw_brief.lower():
        styled_captions = True

    logo_required = True
    if "no logo" in raw_brief.lower() or "logo optional" in raw_brief.lower() or "subtitles are optional" in raw_brief.lower() and "no logo" in raw_brief.lower():
        logo_required = False

    logo_position = "top_right"
    if "bottom_left" in raw_brief.lower() or "bottom left" in raw_brief.lower():
        logo_position = "bottom_left"
    elif "top_left" in raw_brief.lower() or "top left" in raw_brief.lower():
        logo_position = "top_left"
    elif "bottom_right" in raw_brief.lower() or "bottom right" in raw_brief.lower():
        logo_position = "bottom_right"

    return {
        "brand_name": brand_name,
        "campaign_name": campaign_name,
        "source_video_url": source_video_url,
        "logo_url": logo_url,
        "clip_duration": clip_duration,
        "priority_moments": priority_moments,
        "caption_options": caption_options,
        "platform_tags": {
            "tiktok": all_platform_tags,
            "instagram": all_platform_tags,
            "youtube_shorts": all_platform_tags
        },
        "restrictions": {
            "subtitles": "native_preferred",
            "styled_captions": styled_captions,
            "background_music": "allowed_low",
            "logo_required": logo_required,
            "logo_position": "top_right",
            "logo_scale_percent": 0.12,
            "output_format": "blur_pad",
            "other_people_allowed": False,
            "external_footage_allowed": False,
            "filters_allowed": False
        },
        "compliance": {
            "min_days_live": 30,
            "min_engagement_rate": 0.002,
            "likes_must_be_visible": True,
            "tier1_2_audience_required": True,
            "ftc_compliant": True
        }
    }


def parse_brief(raw_brief: str, use_llm: bool = True) -> dict:
    """
    Parse a raw campaign brief string into a CampaignSchema dict.
    If use_llm is True, calls fast LLM; falls back to fast_parse_brief_heuristic on error or timeout.
    If use_llm is False, performs ultra-fast heuristic extraction in <5ms.
    """
    if not use_llm:
        return fast_parse_brief_heuristic(raw_brief)
        
    client = LLMClient()
    prompt = PARSE_PROMPT + raw_brief.strip()
    
    try:
        response = client.call_with_retry(prompt, None, task="summarization")
        if not response:
            raise ValueError("Empty LLM response")
        
        # Strip any accidental markdown wrapper
        cleaned = response.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) > 1:
                cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.rstrip("`").strip()
        else:
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                cleaned = match.group()
        
        parsed = json.loads(cleaned)
        # Ensure clip_duration is valid and sane
        if "clip_duration" in parsed and isinstance(parsed["clip_duration"], dict):
            c_dur = parsed["clip_duration"]
            min_s = float(c_dur.get("min_seconds") or 15.0)
            max_s = float(c_dur.get("max_seconds") or 90.0)
            if max_s < 10.0 or (min_s <= 2.0 and max_s <= 5.0):
                c_dur["min_seconds"] = 15.0
                c_dur["max_seconds"] = 90.0
                c_dur["is_moment_based"] = True
            elif min_s >= max_s:
                c_dur["max_seconds"] = min_s + 45.0
        else:
            parsed["clip_duration"] = extract_clip_duration(raw_brief)

        logger.info(f"Brief parsed successfully with LLM: {parsed.get('campaign_name')}")
        return parsed
        
    except Exception as e:
        logger.warning(f"LLM brief parsing failed ({e}), falling back to regex heuristic parser.")
        return fast_parse_brief_heuristic(raw_brief)
