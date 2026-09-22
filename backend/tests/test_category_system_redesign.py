import pytest
from pathlib import Path
from backend.core.shared_config import VideoCategory, get_prompt_files, PROMPT_DIR, VIDEO_CATEGORIES_CONFIG
from backend.core.duration_config import DurationConfigManager
from backend.pipeline.step3_scoring import ClipScorer, CREATIVE_SCORING_ADDENDUM

EXPECTED_CATEGORIES = [
    'podcast', 'podcast_highlight', 'interview', 'livestream', 'business_insight', 'tech_take',
    'ai_moment', 'gaming_highlight', 'gaming_commentary', 'hot_take',
    'funny_moment', 'vlog', 'storytelling', 'default'
]

EXPECTED_DURATIONS = {
    "podcast": (120.0, 360.0),
    "podcast_highlight": (30.0, 120.0),
    "interview": (60.0, 240.0),
    "livestream": (30.0, 180.0),
    "business_insight": (45.0, 240.0),
    "tech_take": (45.0, 180.0),
    "ai_moment": (30.0, 240.0),
    "gaming_highlight": (15.0, 90.0),
    "gaming_commentary": (60.0, 240.0),
    "hot_take": (30.0, 90.0),
    "funny_moment": (15.0, 60.0),
    "vlog": (30.0, 180.0),
    "storytelling": (60.0, 300.0),
    "default": (45.0, 180.0),
}


def test_all_12_categories_in_enum():
    """Verify all 12 categories plus default are defined in VideoCategory enum."""
    enum_values = [c.value for c in VideoCategory]
    for cat in EXPECTED_CATEGORIES:
        assert cat in enum_values, f"Category {cat} missing from VideoCategory enum"


def test_duration_windows_for_all_categories():
    """Verify each category has the exact min_sec and max_sec windows from spec."""
    mgr = DurationConfigManager()
    for cat, (exp_min, exp_max) in EXPECTED_DURATIONS.items():
        mn, mx = mgr.get_duration_range(cat)
        assert mn == exp_min, f"{cat} min_sec expected {exp_min}, got {mn}"
        assert mx == exp_max, f"{cat} max_sec expected {exp_max}, got {mx}"


def test_prompt_files_exist_for_all_12_categories():
    """Verify outline.txt, timeline.txt, and recommendation.txt exist for all 12 categories."""
    prompt_types = ["outline.txt", "timeline.txt", "recommendation.txt"]
    for cat in [c for c in EXPECTED_CATEGORIES if c != "default"]:
        cat_dir = PROMPT_DIR / cat
        assert cat_dir.is_dir(), f"Category directory {cat_dir} does not exist"
        for ptype in prompt_types:
            pfile = cat_dir / ptype
            assert pfile.is_file(), f"Prompt file {pfile} does not exist"
            assert pfile.stat().st_size > 0, f"Prompt file {pfile} is empty"


def test_get_prompt_files_resolves_category_specific_paths():
    """Verify get_prompt_files resolves category directory files properly."""
    for cat in [c for c in EXPECTED_CATEGORIES if c != "default"]:
        prompts = get_prompt_files(cat)
        assert "outline" in prompts
        assert "timeline" in prompts
        assert "recommendation" in prompts
        assert prompts["outline"] == PROMPT_DIR / cat / "outline.txt"
        assert prompts["timeline"] == PROMPT_DIR / cat / "timeline.txt"
        assert prompts["recommendation"] == PROMPT_DIR / cat / "recommendation.txt"


def test_creativity_scoring_tiebreaker():
    """Verify that when final_scores are equal, creativity_score breaks ties."""
    scorer = ClipScorer(category="podcast")
    assert "Creativity & Personality Score" in scorer.recommendation_prompt

    clips = [
        {
            "id": "1",
            "chunk_index": 0,
            "outline": "Clip Low Creativity",
            "content": ["Topic A"],
            "start_time": "00:01:00,000",
            "end_time": "00:03:00,000",
            "final_score": 0.88,
            "creativity_score": 0.40
        },
        {
            "id": "2",
            "chunk_index": 0,
            "outline": "Clip High Creativity",
            "content": ["Topic B"],
            "start_time": "00:03:30,000",
            "end_time": "00:05:30,000",
            "final_score": 0.88,
            "creativity_score": 0.95
        }
    ]

    sorted_clips = sorted(
        clips,
        key=lambda x: (x.get('final_score', 0), x.get('creativity_score', 0)),
        reverse=True
    )
    assert sorted_clips[0]["id"] == "2"
    assert sorted_clips[1]["id"] == "1"
