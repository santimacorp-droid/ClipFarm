"""
Copy & Text Hook Generator for Short-Form Campaign Clips
Generates:
1. On-Screen Headline Text Hooks (burned into opening 3-5 seconds of video)
2. Search-Optimized Platform Posting Copy (YouTube Shorts, Instagram Reels, TikTok, Facebook)
   specifically optimized for search with common keywords in titles and the first two lines.
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

COPY_PROMPT = """
You are an elite short-form video copywriter and search strategist for YouTube Shorts, Instagram Reels, TikTok, and Facebook.

CRITICAL REQUIREMENT — OPTIMIZE FOR SEARCH:
Viewers use YouTube, TikTok, and Instagram as search engines. You MUST include common keywords and search phrases in your titles and especially in the FIRST TWO LINES of every platform description.
Think about what a real viewer would actually type into the search bar (e.g. "how to build a business", "best AI tools for beginners", "why startup founders fail", "how to make money with AI").

You are given:
- Brand / Creator: {brand_name}
- Moment Name: {moment_name}
- Moment Description: {description}
- Transcript of clip:
\"\"\"{transcript}\"\"\"
- Platform Tags from Brief: {platform_tags}
- Brief Caption Suggestions (if any): {caption_options}

Generate a valid JSON object with the following fields:

1. "hook_text": An on-screen viral text banner (3–7 words, UPPERCASE, creative and directly anchored in what happens in the scene, featuring 1–2 vibrant, contextually relevant emojis, e.g. "BRO REGRETTED THAT FLEX INSTANTLY 💀🔥", "THE KITCHEN TEST CAUSED TOTAL CHAOS 😭👨‍🍳", "3 SECONDS BEFORE DISASTER STRUCK 💀🚨", "THEY PLAYED HIM SO DIRTY 🤯😂"). This text is burned visually at the top of the video in the first 4 seconds. It must create instant curiosity, tension, or comedy.

2. "youtube_shorts":
   - "title": High-CTR, search-optimized title (under 70 characters) containing the exact search query a viewer would type.
   - "caption":
     * Line 1 & Line 2 MUST contain high-volume common search queries and keywords that viewers type into YouTube search.
     * Body: 2-3 sentence punchy summary of what happens in the clip and the key takeaway.
     * Call to action (e.g. "Subscribe for more insights!").
     * Hashtags: #shorts + 3-5 relevant topic hashtags.
   - "tags": space-separated hashtags string including #shorts.

3. "instagram":
   - "caption":
     * Line 1: Scroll-stopping hook before the fold (<125 characters) with natural search keywords (Instagram SEO indexer).
     * Line 2: Follow-up tension or value proposition.
     * Body: Engaging, readable paragraph with line breaks.
     * Discussion question & Call to Action (e.g. "Save this for later & share your thoughts below!").
     * Clean hashtag cloud (5-8 niche tags).
   - "tags": space-separated hashtags string.

4. "tiktok":
   - "caption":
     * Line 1 & Line 2: TikTok SEO-optimized (uses exact keyword phrases people search on TikTok).
     * Punchy, conversational hook.
     * Clear CTA.
     * Hashtags (#fyp #viral + niche tags + brand tag).
   - "tags": space-separated hashtags string.

5. "facebook":
   - "title": Scroll-stopping headline.
   - "caption":
     * Line 1 & Line 2: Conversational hook with common search keywords that stop the feed scroll.
     * Relatable context and key insight.
     * Discussion prompt to drive comments and shares (e.g. "Have you experienced this? Let me know below!").
     * Clean hashtags.
   - "tags": space-separated hashtags string.

Return ONLY the valid JSON object. No explanation, no markdown backticks, no code block wrapper.
"""


def _clean_json_response(raw_text: str) -> str:
    """Strip markdown code block fences if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_core_keywords(text: str, max_words: int = 4) -> str:
    """Extract top 2-4 meaningful keywords from text for search phrase synthesis."""
    stop_words = {
        'the', 'and', 'for', 'are', 'was', 'its', 'you', 'this', 'that', 'with',
        'from', 'your', 'what', 'just', 'now', 'can', 'has', 'not', 'have', 'how',
        'why', 'about', 'when', 'will', 'then', 'into', 'some', 'more', 'their',
        'clip', 'moment', 'starts', 'video', 'watch', 'episode'
    }
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    seen = set()
    unique = []
    for w in filtered:
        if w not in seen:
            seen.add(w)
            unique.append(w)
            if len(unique) >= max_words:
                break
    return " ".join(unique) if unique else "this topic"


def _heuristic_fallback_copy(
    moment_name: str,
    transcript_text: str,
    brand_name: str = "Brand",
    platform_tags: Optional[Dict[str, List[str]]] = None,
    caption_options: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Deterministic fallback that strictly fulfills:
    1. 3-6 word uppercase text hook
    2. Common search keywords in title and the first two lines of descriptions
    3. Dedicated copy for YouTube Shorts, Instagram, TikTok, and Facebook
    """
    platform_tags = platform_tags or {}
    tags_tiktok = " ".join(platform_tags.get("tiktok", []))
    tags_ig = " ".join(platform_tags.get("instagram", []))
    tags_yt = " ".join(platform_tags.get("youtube_shorts", []))
    tags_fb = " ".join(platform_tags.get("facebook", []))

    brand_clean = re.sub(r'[^a-zA-Z0-9]', '', brand_name)
    brand_tag = f"#{brand_clean}" if brand_clean else ""

    # Synthesize keyword phrase
    keywords = _extract_core_keywords(f"{moment_name} {transcript_text[:300]}")
    keyword_title = keywords.title() if keywords else moment_name

    # Synthesize uppercase text hook (3-7 words with vibrant emojis)
    hook_candidates = [
        f"THE TRUTH ABOUT {keywords.upper()[:22]} 💀🔥",
        "STOP DOING THIS RIGHT NOW 🚨",
        "WHY NOBODY TALKS ABOUT THIS 🤫⚡",
        "DO NOT MAKE THIS MISTAKE 🤯❌",
        "THE BRUTAL TRUTH ABOUT THIS 💀🔥"
    ]
    hook_text = hook_candidates[0] if len(keywords.split()) <= 3 else "THE BRUTAL TRUTH ABOUT THIS 💀🔥"

    # Base caption from options or moment name
    chosen = caption_options[0] if caption_options else moment_name

    # YouTube Shorts: Search intent in line 1 & line 2
    yt_title = f"The Truth About {keyword_title}"[:70]
    yt_caption = (
        f"Looking for the best way to understand {keywords}?\n"
        f"Here is what you actually need to know about {moment_name}.\n\n"
        f"{chosen}\n\n"
        f"Subscribe for more daily breakdowns!\n\n"
        f"#shorts {brand_tag} {tags_yt}".strip()
    )

    # Instagram Reels: Line 1 hook (<125 chars) + Line 2 search keywords
    ig_caption = (
        f"The #1 thing people get wrong about {keywords} 👇\n"
        f"If you've been searching for real answers on {moment_name}, watch this.\n\n"
        f"{chosen}\n\n"
        f"Save this for later & share with someone who needs to hear it!\n\n"
        f"{brand_tag} {tags_ig}".strip()
    )

    # TikTok: Line 1 & 2 TikTok search query phrasing
    tiktok_caption = (
        f"POV: You finally found the real answer to {keywords} 🤯\n"
        f"Search no further — here is the breakdown on {moment_name}.\n\n"
        f"{chosen}\n\n"
        f"#fyp #viral #trending {brand_tag} {tags_tiktok}".strip()
    )

    # Facebook: Line 1 & 2 conversational search hook + comment prompt
    fb_title = f"Why Nobody Talks About {keyword_title}"[:70]
    fb_caption = (
        f"This changed how I look at {keywords} completely.\n"
        f"Most people never realize this until it's too late — here is what happens with {moment_name}.\n\n"
        f"{chosen}\n\n"
        f"Have you experienced this? Drop your thoughts in the comments below!\n\n"
        f"{brand_tag} {tags_fb}".strip()
    )

    return {
        "hook_text": hook_text,
        "youtube_shorts": {
            "title": yt_title,
            "caption": yt_caption,
            "tags": f"#shorts {tags_yt} {brand_tag}".strip()
        },
        "instagram": {
            "caption": ig_caption,
            "tags": f"{tags_ig} {brand_tag}".strip()
        },
        "tiktok": {
            "caption": tiktok_caption,
            "tags": f"#fyp #viral {tags_tiktok} {brand_tag}".strip()
        },
        "facebook": {
            "title": fb_title,
            "caption": fb_caption,
            "tags": f"{tags_fb} {brand_tag}".strip()
        }
    }


def generate_clip_copy_and_hook(
    moment_name: str,
    transcript_text: str,
    brand_name: str = "Brand",
    description: str = "",
    platform_tags: Optional[Dict[str, List[str]]] = None,
    caption_options: Optional[List[str]] = None,
    llm_client: Optional[LLMClient] = None
) -> Dict[str, Any]:
    """
    Main entry point: Generates viral on-screen hook and search-optimized copy
    for YouTube Shorts, Instagram Reels, TikTok, and Facebook.
    Falls back gracefully to deterministic search-optimized copy on any failure.
    """
    platform_tags = platform_tags or {}
    caption_options = caption_options or []

    prompt = COPY_PROMPT.format(
        brand_name=brand_name or "Brand",
        moment_name=moment_name or "Clip",
        description=description or "",
        transcript=transcript_text[:1200] if transcript_text else "No transcript available",
        platform_tags=json.dumps(platform_tags),
        caption_options=json.dumps(caption_options)
    )

    try:
        client = llm_client or LLMClient()
        raw_response = client.call_with_retry(prompt, None, task="titling")
        if raw_response:
            clean_json = _clean_json_response(raw_response)
            parsed = json.loads(clean_json)

            if isinstance(parsed, dict) and "hook_text" in parsed:
                hook = str(parsed.get("hook_text", "")).strip().upper()
                hook = re.sub(r'[\.\!]+$', '', hook).strip()
                if not hook:
                    hook = "WATCH THIS"

                yt = parsed.get("youtube_shorts", {})
                ig = parsed.get("instagram", {})
                tt = parsed.get("tiktok", {})
                fb = parsed.get("facebook", {})

                tags_tiktok = " ".join(platform_tags.get("tiktok", []))
                tags_ig = " ".join(platform_tags.get("instagram", []))
                tags_yt = " ".join(platform_tags.get("youtube_shorts", []))
                tags_fb = " ".join(platform_tags.get("facebook", []))

                return {
                    "hook_text": hook,
                    "youtube_shorts": {
                        "title": str(yt.get("title") or moment_name[:70]).strip(),
                        "caption": str(yt.get("caption") or "").strip(),
                        "tags": str(yt.get("tags") or f"#shorts {tags_yt}").strip()
                    },
                    "instagram": {
                        "caption": str(ig.get("caption") or "").strip(),
                        "tags": str(ig.get("tags") or tags_ig).strip()
                    },
                    "tiktok": {
                        "caption": str(tt.get("caption") or "").strip(),
                        "tags": str(tt.get("tags") or f"#fyp #viral {tags_tiktok}").strip()
                    },
                    "facebook": {
                        "title": str(fb.get("title") or moment_name[:70]).strip(),
                        "caption": str(fb.get("caption") or "").strip(),
                        "tags": str(fb.get("tags") or tags_fb).strip()
                    }
                }
    except Exception as e:
        logger.warning(f"LLM copy generation failed ({e}) — utilizing search-optimized heuristic fallback")

    return _heuristic_fallback_copy(
        moment_name=moment_name,
        transcript_text=transcript_text,
        brand_name=brand_name,
        platform_tags=platform_tags,
        caption_options=caption_options
    )
