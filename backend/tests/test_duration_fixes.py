"""
Tests for Phase 1: Category-Aware Duration Fixes, Boundary Merging, and Regression Canary
"""

import pytest
import logging
from backend.core.duration_config import duration_config
from backend.core.shared_config import get_clip_duration_limits
from backend.pipeline.step2_timeline import TimelineExtractor
from backend.pipeline.step3_scoring import ClipScorer
from backend.services.simple_pipeline_adapter import check_duration_regression_canary


def test_category_duration_table_resolution():
    """Verify that category duration limits permit up to 8 minutes (480s)."""
    # Speech allows up to 8 minutes (480s)
    sp_min, sp_max = duration_config.get_duration_range("speech")
    assert sp_min == 120.0
    assert sp_max == 480.0

    # Tutorial allows up to 6 minutes (360s)
    tut_min, tut_max = duration_config.get_duration_range("tutorial")
    assert tut_min == 120.0
    assert tut_max == 360.0

    # Story allows up to 5 minutes (300s)
    st_min, st_max = duration_config.get_duration_range("story")
    assert st_min == 90.0
    assert st_max == 300.0

    # Entertainment caps at 90s
    ent_min, ent_max = duration_config.get_duration_range("entertainment")
    assert ent_min == 30.0
    assert ent_max == 90.0

    # Default / general
    def_min, def_max = duration_config.get_duration_range("default")
    assert def_min == 45.0
    assert def_max == 180.0

    # Verify delegation in shared_config
    assert get_clip_duration_limits("speech") == (120.0, 480.0)


def test_merge_adjacent_segments(tmp_path):
    """Verify merge_adjacent_segments fuses consecutive segments on same topic across boundaries."""
    extractor = TimelineExtractor(metadata_dir=tmp_path, category="speech")

    timeline_items = [
        {
            "id": "1",
            "outline": "The Deep AI Revolution (Part 1)",
            "start_time": "00:01:00,000",
            "end_time": "00:03:00,000",  # 2m
            "content": ["First half of the argument"]
        },
        {
            "id": "2",
            "outline": "The Deep AI Revolution (Part 2)",
            "start_time": "00:03:05,000",  # 5s gap
            "end_time": "00:06:30,000",  # 3m25s
            "content": ["Second half and conclusion"]
        },
        {
            "id": "3",
            "outline": "Unrelated Topic on Economy",
            "start_time": "00:07:00,000",
            "end_time": "00:09:00,000",
            "content": ["Economy insight"]
        }
    ]

    merged = extractor.merge_adjacent_segments(timeline_items, category="speech")
    assert len(merged) == 2

    # Segments 1 and 2 merged into a 5m30s segment (330s)
    first_clip = merged[0]
    assert first_clip["start_time"] == "00:01:00,000"
    assert first_clip["end_time"] == "00:06:30,000"
    assert len(first_clip["content"]) == 2

    # Clip 3 remained intact
    assert merged[1]["outline"] == "Unrelated Topic on Economy"


def test_calculate_duration_appropriateness():
    """Verify duration-appropriateness score rewards multi-minute story/speech clips."""
    scorer = ClipScorer(category="story")

    # A 4-minute (240s) story clip falls perfectly inside [90s, 300s]
    score_4m = scorer.calculate_duration_appropriateness(240.0, category="story")
    assert score_4m == 1.0

    # A 6-minute (360s) speech clip falls perfectly inside [120s, 480s]
    score_6m = scorer.calculate_duration_appropriateness(360.0, category="speech")
    assert score_6m == 1.0

    # A 15s snippet for speech is heavily undersized
    score_tiny = scorer.calculate_duration_appropriateness(15.0, category="speech")
    assert score_tiny < 0.70


def test_regression_canary_triggers_on_suspiciously_short(caplog):
    """Verify regression canary emits warning if >80% of clips are under 75s."""
    short_clips = [
        {"start_time": "00:00:10,000", "end_time": "00:01:05,000"},  # 55s
        {"start_time": "00:02:10,000", "end_time": "00:03:00,000"},  # 50s
        {"start_time": "00:04:10,000", "end_time": "00:05:00,000"},  # 50s
        {"start_time": "00:06:10,000", "end_time": "00:07:00,000"},  # 50s
        {"start_time": "00:08:10,000", "end_time": "00:10:00,000"},  # 110s
    ]

    with caplog.at_level(logging.WARNING):
        check_duration_regression_canary(short_clips, stage_name="Test Short")

    assert "WARNING: clip duration distribution looks suspiciously short" in caplog.text


def test_regression_canary_passes_on_healthy_distribution(caplog):
    """Verify regression canary does NOT warn when multi-minute clips are present."""
    healthy_clips = [
        {"start_time": "00:00:10,000", "end_time": "00:02:30,000"},  # 140s
        {"start_time": "00:03:00,000", "end_time": "00:06:00,000"},  # 180s
        {"start_time": "00:07:00,000", "end_time": "00:12:00,000"},  # 300s
        {"start_time": "00:13:00,000", "end_time": "00:13:45,000"},  # 45s
    ]

    with caplog.at_level(logging.WARNING):
        check_duration_regression_canary(healthy_clips, stage_name="Test Healthy")

    assert "WARNING: clip duration distribution looks suspiciously short" not in caplog.text
