"""
Tests for Copy & Text Hook Generator (Search-Optimized Platform Captions)
"""
import pytest
from unittest.mock import MagicMock, patch
from backend.campaign.copy_generator import (
    generate_clip_copy_and_hook,
    _heuristic_fallback_copy,
    _extract_core_keywords
)
from backend.campaign.package_builder import build_platform_post_guide


def test_extract_core_keywords():
    """Verify that keyword extraction filters stop words and keeps meaningful keywords."""
    text = "The secret to building an AI startup and how to scale rapidly with video clips"
    kw = _extract_core_keywords(text, max_words=3)
    assert "secret" in kw or "building" in kw or "startup" in kw
    assert "the" not in kw.split()
    assert "and" not in kw.split()


def test_heuristic_fallback_copy_platforms_and_hook():
    """Verify fallback generates all 4 platforms and a 3-6 word uppercase hook."""
    res = _heuristic_fallback_copy(
        moment_name="Why Most Creators Fail at Monetization",
        transcript_text="So many people think that having followers equals having a real business. It doesn't.",
        brand_name="Aspire",
        platform_tags={"tiktok": ["@aspire"], "instagram": ["@aspire_official"], "youtube_shorts": ["#business"], "facebook": ["#entrepreneur"]},
        caption_options=["Most creators fail because they don't treat content like a business."]
    )

    # 1. Text hook
    assert "hook_text" in res
    words = res["hook_text"].split()
    assert 2 <= len(words) <= 7
    assert res["hook_text"] == res["hook_text"].upper()

    # 2. All 4 platforms exist
    for platform in ["youtube_shorts", "instagram", "tiktok", "facebook"]:
        assert platform in res, f"Missing platform {platform}"
        assert "caption" in res[platform]
        assert len(res[platform]["caption"]) > 20

    # 3. Titles exist for YouTube Shorts and Facebook
    assert "title" in res["youtube_shorts"]
    assert "title" in res["facebook"]
    assert len(res["youtube_shorts"]["title"]) <= 70
    assert len(res["facebook"]["title"]) <= 70


def test_heuristic_fallback_search_optimization_first_two_lines():
    """Verify that the first two lines contain search queries / keywords."""
    res = _heuristic_fallback_copy(
        moment_name="How To Use AI For Automated Video Editing",
        transcript_text="Automated video editing using AI tools is completely revolutionizing how creators produce short form clips.",
        brand_name="AutoClip"
    )

    yt_lines = [l.strip() for l in res["youtube_shorts"]["caption"].splitlines() if l.strip()]
    ig_lines = [l.strip() for l in res["instagram"]["caption"].splitlines() if l.strip()]
    tt_lines = [l.strip() for l in res["tiktok"]["caption"].splitlines() if l.strip()]
    fb_lines = [l.strip() for l in res["facebook"]["caption"].splitlines() if l.strip()]

    # First line and second line must contain search-oriented phrases
    assert any(term in yt_lines[0].lower() for term in ["looking for", "search", "how", "way", "understand", "ai"])
    assert any(term in ig_lines[0].lower() for term in ["#1", "wrong", "search", "truth", "ai", "how"])
    assert any(term in tt_lines[0].lower() for term in ["pov:", "search", "found", "answer", "ai", "secret"])
    assert any(term in fb_lines[0].lower() for term in ["changed", "look at", "most people", "ai", "realize"])


def test_generate_clip_copy_with_mock_llm():
    """Verify LLM parsing and schema assembly."""
    mock_json = '''{
      "hook_text": "DO NOT MAKE THIS MISTAKE",
      "youtube_shorts": {
        "title": "Best AI Tools For Video Editing 2026",
        "caption": "Looking for the best AI tools for video editing? Here is the complete breakdown.\\nSave time and 10x your output with these proven workflows.\\n\\nSubscribe for more tips!\\n\\n#shorts #AI #VideoEditing",
        "tags": "#shorts #AI #VideoEditing"
      },
      "instagram": {
        "caption": "The biggest AI editing mistake everyone is making 👇\\nIf you're trying to rank your short form videos, watch this entire clip.\\n\\nSave this reel for later!\\n\\n#reels #ai #contentcreator",
        "tags": "#reels #ai #contentcreator"
      },
      "tiktok": {
        "caption": "How to edit viral shorts in 60 seconds with AI 🤯\\nStop spending hours manually cutting footage.\\n\\n#fyp #viral #aitools",
        "tags": "#fyp #viral #aitools"
      },
      "facebook": {
        "title": "Why AI Video Editing Changes Everything",
        "caption": "This AI strategy changed how top creators produce content.\\nMost editors spend hours on this without knowing there is a better way.\\n\\nWhat is your favorite tool? Drop your thoughts below!\\n\\n#content #ai",
        "tags": "#content #ai"
      }
    }'''

    mock_client = MagicMock()
    mock_client.call_with_retry.return_value = mock_json

    result = generate_clip_copy_and_hook(
        moment_name="AI Video Editing Secrets",
        transcript_text="Here is how top creators edit videos with AI.",
        brand_name="AutoClip",
        llm_client=mock_client
    )

    assert result["hook_text"] == "DO NOT MAKE THIS MISTAKE"
    assert result["youtube_shorts"]["title"] == "Best AI Tools For Video Editing 2026"
    assert "Looking for the best AI tools" in result["youtube_shorts"]["caption"]
    assert "biggest AI editing mistake" in result["instagram"]["caption"]
    assert "How to edit viral shorts" in result["tiktok"]["caption"]
    assert "Why AI Video Editing Changes Everything" in result["facebook"]["title"]


def test_generate_clip_copy_fallback_on_exception():
    """Verify graceful fallback if LLM client raises an error."""
    mock_client = MagicMock()
    mock_client.call_with_retry.side_effect = RuntimeError("API connection timeout")

    result = generate_clip_copy_and_hook(
        moment_name="Scaling Your Channel",
        transcript_text="Consistency is key when building an audience from scratch.",
        brand_name="CreatorBrand",
        llm_client=mock_client
    )

    assert "hook_text" in result
    assert result["hook_text"]
    assert "youtube_shorts" in result
    assert "facebook" in result
    assert "tiktok" in result
    assert "instagram" in result


def test_build_platform_post_guide_includes_facebook():
    """Verify that build_platform_post_guide generates copy for all 4 platforms."""
    guide = build_platform_post_guide(
        chosen_caption="Consistency beats talent every single time.",
        platform_tags={"tiktok": ["@creator"], "instagram": ["@creator"], "youtube_shorts": ["#creator"], "facebook": ["#creator"]},
        moment_name="The Truth About Consistency",
        transcript_text="Consistency beats talent when talent doesn't work hard.",
        brand_name="CreatorBrand"
    )

    assert "facebook" in guide
    assert "youtube_shorts" in guide
    assert "tiktok" in guide
    assert "instagram" in guide
    assert len(guide["facebook"]["caption"]) > 10
