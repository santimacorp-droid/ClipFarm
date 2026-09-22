import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.utils.social_caption_generator import (
    SocialCaptionGenerator,
    CATEGORY_HASHTAG_BANKS
)


def _create_sample_srt(srt_path: Path):
    content = """1
00:00:01,000 --> 00:00:04,000
Welcome back everyone to our deep dive on the Apple M4 chip.

2
00:00:04,500 --> 00:00:09,000
In today's test, the single core benchmark completely shocked our engineering team.

3
00:00:09,500 --> 00:00:15,000
Intel's flagship desktop processor couldn't even match the power efficiency of this silicon.

4
00:00:16,000 --> 00:00:20,000
Moving on to the next segment of our podcast episode.
"""
    srt_path.write_text(content, encoding="utf-8")


def test_extract_clip_transcript():
    with tempfile.TemporaryDirectory() as tmp:
        srt_file = Path(tmp) / "input.srt"
        _create_sample_srt(srt_file)

        # Extract dialogue within 4.0 to 10.0 seconds
        transcript = SocialCaptionGenerator.extract_clip_transcript(srt_file, start_sec=4.0, end_sec=10.0)
        assert "single core benchmark" in transcript
        assert "power efficiency" in transcript
        assert "Moving on to the next segment" not in transcript


def test_extract_core_entities():
    sample_text = "Why the M4 chip crushed Intel desktop lineup in benchmark tests with Robin Williams"
    entities = SocialCaptionGenerator.extract_core_entities(sample_text)
    assert any("m4" in e.lower() for e in entities) or any("intel" in e.lower() for e in entities)


def test_build_hashtags():
    # Tech category
    tech_tags = SocialCaptionGenerator.build_hashtags(category="tech_take", entities=["m4", "apple"], max_tags=6)
    assert "#shorts" in tech_tags
    assert "#reels" in tech_tags
    assert any("tech" in t.lower() for t in tech_tags)
    assert "#m4" in tech_tags or "#apple" in tech_tags
    assert len(tech_tags) <= 6

    # Podcast category
    pod_tags = SocialCaptionGenerator.build_hashtags(category="podcast", entities=["interview"], max_tags=5)
    assert "#podcast" in pod_tags or "#podcastclips" in pod_tags


def test_fallback_caption_dual_context():
    gen = SocialCaptionGenerator()
    clip_data = {
        "id": "1",
        "title": "M4 Single Core Performance Shocked Engineers",
        "generated_title": "M4 Single Core Performance Shocked Engineers",
        "hook_text": "THIS BENCHMARK CHANGED EVERYTHING 🤯",
        "category": "tech_take",
        "start_time": "00:00:04,500",
        "end_time": "00:00:15,000",
        "content": ["M4 outperforms desktop class chips in single core tasks."]
    }
    global_context = {
        "video_title": "Apple M4 Full Architecture Breakdown",
        "video_category": "tech_take"
    }
    fallback = gen._generate_fallback_caption(
        clip_data=clip_data,
        global_context=global_context,
        clip_transcript="In today's test, the single core benchmark completely shocked our engineering team."
    )

    # Verify structure
    assert "hook_line" in fallback
    assert fallback["hook_line"] == "THIS BENCHMARK CHANGED EVERYTHING 🤯"
    assert "post_caption" in fallback
    assert "Apple M4 Full Architecture Breakdown" in fallback["post_caption"]
    assert "M4 Single Core Performance" in fallback["post_caption"]
    assert "platforms" in fallback
    assert "tiktok" in fallback["platforms"]
    assert "instagram" in fallback["platforms"]
    assert "youtube_shorts" in fallback["platforms"]
    assert len(fallback["hashtags"]) >= 4


def test_generate_social_caption_with_mock_llm():
    gen = SocialCaptionGenerator()
    
    mock_llm_json = {
        "hook_line": "The M4 single core score just broke the internet.",
        "post_caption": "The M4 single core score just broke the internet.\n\nFrom our full deep-dive on Apple silicon, we tested the limits against desktop competitors.\n\nWould you switch your primary rig for this? Drop your thoughts below 👇\n\n#shorts #techtok #apple #m4",
        "hashtags": ["#shorts", "#techtok", "#apple", "#m4"],
        "engagement_question": "Would you switch your primary rig for this? Drop your thoughts below 👇",
        "search_keywords": ["apple m4 benchmark", "m4 single core test"],
        "platforms": {
            "tiktok": {
                "caption": "The M4 single core score broke the internet. Full test vs Intel!",
                "hashtags": "#fyp #techtok #m4"
            },
            "instagram": {
                "caption": "The M4 single core score just broke the internet.\n\nFull deep dive on Apple silicon.\n\n👇",
                "hashtags": "#reels #apple #techtok"
            },
            "youtube_shorts": {
                "title": "Why the M4 Chip Shocked Engineers",
                "description": "Full benchmark breakdown of Apple's latest chip.",
                "hashtags": "#shorts #techtok"
            }
        }
    }

    with patch.object(gen.llm_client, 'call_with_retry', return_value='dummy_raw'):
        with patch.object(gen.llm_client, 'parse_json_response', return_value=mock_llm_json):
            clip_data = {
                "id": "1",
                "title": "M4 Test",
                "start_time": 4.5,
                "end_time": 15.0
            }
            res = gen.generate_social_caption(clip_data, global_context={"video_title": "Full M4 Review"})
            assert res["hook_line"] == "The M4 single core score just broke the internet."
            assert "platforms" in res
            assert res["platforms"]["tiktok"]["hashtags"] == "#fyp #techtok #m4"


def test_batch_generate_social_captions():
    gen = SocialCaptionGenerator()
    clips = [
        {
            "id": "1",
            "title": "Clip 1 Title",
            "hook_text": "HOOK 1",
            "start_time": "00:00:00,000",
            "end_time": "00:00:10,000",
            "content": ["Highlights 1"]
        },
        {
            "id": "2",
            "title": "Clip 2 Title",
            "hook_text": "HOOK 2",
            "start_time": "00:00:10,000",
            "end_time": "00:00:20,000",
            "content": ["Highlights 2"]
        }
    ]
    global_context = {
        "video_title": "Full Podcast Episode 42",
        "video_category": "podcast"
    }

    # Batch generate using fallback mode (no LLM calls needed)
    with patch.object(gen, 'generate_social_caption', side_effect=lambda c, g, s, m: gen._generate_fallback_caption(c, g)):
        result = gen.batch_generate_social_captions(clips, global_context)
        assert len(result) == 2
        for c in result:
            assert "social_copy" in c
            assert "post_caption" in c
            assert "hashtags" in c
            assert len(c["hashtags"]) > 0
            assert "Full Podcast Episode 42" in c["social_copy"]["post_caption"]
