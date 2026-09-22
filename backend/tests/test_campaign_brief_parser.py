"""Tests for campaign brief parser."""
import pytest
from backend.campaign.brief_parser import parse_brief

FRIDA_BRIEF = """
Frida - Dr. Rosen Episode 1 Clipping
Clip moments from the 54-second Dr. Rosen segment. Clips should be 15-40 seconds.
Moments to prioritize:
- The ant and the cookie — starts "Think of your fungus and your bacteria as ants."
CAPTION GUIDELINES
- The ant and the cookie thing is going to live rent-free in my head.
- Looking clean and being clean are not the same thing.
TAGGING REQUIREMENT: TikTok: tag @frida
LOGO REQUIREMENT: Add the Frida logo. Logo file: https://drive.google.com/file/d/abc123
"""

def test_parse_brief_returns_dict():
    # Mock LLM call to avoid real API call in tests
    from unittest.mock import patch, MagicMock
    mock_response = '''{
      "brand_name": "Frida",
      "campaign_name": "Frida - Dr. Rosen Episode 1 Clipping",
      "source_video_url": null,
      "logo_url": "https://drive.google.com/file/d/abc123",
      "clip_duration": {"min_seconds": 15, "max_seconds": 40},
      "priority_moments": [
        {"name": "The ant and the cookie", "start_line": "Think of your fungus and your bacteria as ants."}
      ],
      "caption_options": ["The ant and the cookie thing is going to live rent-free in my head."],
      "platform_tags": {"tiktok": ["@frida"], "instagram": [], "youtube_shorts": []},
      "restrictions": {"subtitles": "native_preferred", "styled_captions": false,
                       "background_music": "allowed_low", "logo_required": true,
                       "logo_position": "top_right", "logo_scale_percent": 0.12,
                       "other_people_allowed": false, "external_footage_allowed": false,
                       "filters_allowed": false},
      "compliance": {"min_days_live": 30, "min_engagement_rate": 0.002,
                     "likes_must_be_visible": true, "tier1_2_audience_required": true,
                     "ftc_compliant": true}
    }'''
    
    with patch('backend.campaign.brief_parser.LLMClient') as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.call_with_retry.return_value = mock_response
        mock_llm_cls.return_value = mock_llm
        
        result = parse_brief(FRIDA_BRIEF)
    
    assert result['brand_name'] == 'Frida'
    assert result['clip_duration']['min_seconds'] == 15
    assert result['clip_duration']['max_seconds'] == 40
    assert len(result['priority_moments']) >= 1
    assert result['restrictions']['styled_captions'] == False
    assert result['restrictions']['logo_required'] == True


def test_parse_brief_fallback_on_llm_failure():
    """Parser returns minimal schema on LLM failure, does not crash."""
    from unittest.mock import patch, MagicMock
    
    with patch('backend.campaign.brief_parser.LLMClient') as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.call_with_retry.side_effect = Exception("API error")
        mock_llm_cls.return_value = mock_llm
        
        result = parse_brief("some brief text")
    
    assert 'brand_name' in result
    assert 'clip_duration' in result
    assert 'restrictions' in result


def test_extract_clip_duration_with_tier1_2_countries():
    """Verify that 'Tier 1–2 countries' is not mistaken for a 1s-2s duration."""
    from backend.campaign.brief_parser import extract_clip_duration
    
    brief = """
    Page audience should primarily be Tier 1–2 countries (30%+ Tier 3 may be removed)
    Video must be AT LEAST 10 seconds long
    """
    dur = extract_clip_duration(brief)
    assert dur['min_seconds'] == 10.0
    assert dur['max_seconds'] >= 60.0
    assert dur['is_moment_based'] == True
    assert (dur['min_seconds'], dur['max_seconds']) != (1.0, 2.0)


def test_extract_clip_duration_moment_based_default():
    """Verify that briefs without seconds default to moment-based."""
    from backend.campaign.brief_parser import extract_clip_duration
    
    brief = "Clip standout moments across the podcast episode."
    dur = extract_clip_duration(brief)
    assert dur['min_seconds'] == 15.0
    assert dur['max_seconds'] == 90.0
    assert dur['is_moment_based'] == True


def test_heuristic_parser_filters_instructions_from_moments():
    """Verify that editing instructions like 'Lead with strongest moment' are not parsed as moments."""
    from backend.campaign.brief_parser import fast_parse_brief_heuristic
    
    brief = """
    Prioritize moments with:
    • Strong, provocative hooks that immediately create curiosity
    • Actionable business or leadership advice
    • Lead with the strongest moment immediately — avoid long intros, guest bios
    • Experiment with different hooks, lengths, edits across the episode
    • Post to TikTok and Instagram
    """
    result = fast_parse_brief_heuristic(brief)
    moment_names = [m['name'].lower() for m in result['priority_moments']]
    
    assert any('strong, provocative hooks' in n for n in moment_names)
    assert any('actionable business' in n for n in moment_names)
    # Instructions must be excluded
    assert not any('lead with the strongest moment' in n for n in moment_names)
    assert not any('experiment with different hooks' in n for n in moment_names)
    assert not any('post to tiktok' in n for n in moment_names)


def test_clip_duration_pydantic_validator():
    """Verify that ClipDuration model validator automatically corrects invalid <10s durations."""
    from backend.schemas.campaign import ClipDuration
    
    # 1s - 2s should be corrected
    cd = ClipDuration(min_seconds=1.0, max_seconds=2.0)
    assert cd.min_seconds == 15.0
    assert cd.max_seconds == 90.0
    assert cd.is_moment_based == True
    
    # Valid explicit duration should be preserved
    cd2 = ClipDuration(min_seconds=15.0, max_seconds=40.0, is_moment_based=False)
    assert cd2.min_seconds == 15.0
    assert cd2.max_seconds == 40.0
    assert cd2.is_moment_based == False
