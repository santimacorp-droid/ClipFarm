import pytest
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.pipeline.step2_timeline import TimelineExtractor
from backend.core.shared_config import (
    MIN_CLIP_DURATION,
    MAX_CLIP_DURATION,
    get_clip_duration_limits
)
from backend.utils.text_processor import TextProcessor


@pytest.fixture
def temp_metadata_dir(tmp_path):
    """Set up temporary directory with necessary step1 mock chunks."""
    meta_dir = tmp_path / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    srt_chunks_dir = meta_dir / "step1_srt_chunks"
    srt_chunks_dir.mkdir(parents=True, exist_ok=True)
    
    # 30-minute SRT chunk (00:00:00 to 00:30:00)
    chunk_0_data = [
        {"index": 1, "start_time": "00:00:00,000", "end_time": "00:00:05,000", "text": "Intro"},
        {"index": 2, "start_time": "00:29:50,000", "end_time": "00:30:00,000", "text": "Outro"}
    ]
    with open(srt_chunks_dir / "chunk_0.json", "w", encoding="utf-8") as f:
        json.dump(chunk_0_data, f)
        
    return meta_dir


def test_shared_config_category_bounds():
    """Verify get_clip_duration_limits returns correct category-calibrated bounds."""
    default_min, default_max = get_clip_duration_limits("default")
    assert default_min == 45.0
    assert default_max == 180.0

    speech_min, speech_max = get_clip_duration_limits("speech")
    assert speech_min == 120.0
    assert speech_max == 480.0

    ent_min, ent_max = get_clip_duration_limits("entertainment")
    assert ent_min == 30.0
    assert ent_max == 90.0

    # Unknown category falls back to defaults
    unk_min, unk_max = get_clip_duration_limits("nonexistent_category")
    assert unk_min == 45.0
    assert unk_max == 180.0


def test_step2_natural_durations_preserved(temp_metadata_dir, caplog):
    """
    Verify that Step 2 preserves natural clip durations across category windows
    (e.g., up to 480s for speech, 300s for story).
    """
    outlines = [
        {"title": "Story Beat (95s)", "subtopics": ["Hook", "Action"], "chunk_index": 0},
        {"title": "Focused Story (150s)", "subtopics": ["Concept", "Resolution"], "chunk_index": 0},
        {"title": "Long Multi-Beat Story (280s)", "subtopics": ["Epic narrative", "Conclusion"], "chunk_index": 0},
    ]

    llm_simulated_response = json.dumps([
        {"id": "1", "outline": "Story Beat (95s)", "start_time": "00:01:00,000", "end_time": "00:02:35,000", "content": ["Hook"]},
        {"id": "2", "outline": "Focused Story (150s)", "start_time": "00:03:00,000", "end_time": "00:05:30,000", "content": ["Concept"]},
        {"id": "3", "outline": "Long Multi-Beat Story (280s)", "start_time": "00:06:00,000", "end_time": "00:10:40,000", "content": ["Epic narrative"]},
    ])

    extractor = TimelineExtractor(metadata_dir=temp_metadata_dir, category="story")
    extractor.llm_client.call_with_retry = MagicMock(return_value=llm_simulated_response)

    with caplog.at_level(logging.INFO):
        results = extractor.extract_timeline(outlines)

    tp = TextProcessor()
    durations = [tp.time_to_seconds(item['end_time']) - tp.time_to_seconds(item['start_time']) for item in results]

    # Under story (90s to 300s), all 3 preserve their natural durations:
    assert durations == [95.0, 150.0, 280.0]
    assert "preserved natural duration: 95.0s" in caplog.text
    assert "preserved natural duration: 150.0s" in caplog.text
    assert "preserved natural duration: 280.0s" in caplog.text


def test_step2_under_min_and_over_max_clamping(temp_metadata_dir, caplog):
    """
    Verify that clips below min_duration are adjusted and clips above max_duration are clamped,
    with explicit warnings logged.
    """
    outlines = [
        {"title": "Tiny Fragment (5s)", "subtopics": ["Too short"], "chunk_index": 0},
        {"title": "Runaway Segment (320s)", "subtopics": ["Too long"], "chunk_index": 0},
    ]

    llm_simulated_response = json.dumps([
        {"id": "1", "outline": "Tiny Fragment (5s)", "start_time": "00:01:00,000", "end_time": "00:01:05,000", "content": ["Too short"]},
        {"id": "2", "outline": "Runaway Segment (320s)", "start_time": "00:05:00,000", "end_time": "00:10:20,000", "content": ["Too long"]},
    ])

    extractor = TimelineExtractor(metadata_dir=temp_metadata_dir, category="default")
    extractor.llm_client.call_with_retry = MagicMock(return_value=llm_simulated_response)

    with caplog.at_level(logging.WARNING):
        results = extractor.extract_timeline(outlines)

    tp = TextProcessor()
    durations = [tp.time_to_seconds(item['end_time']) - tp.time_to_seconds(item['start_time']) for item in results]

    # Default category: min 45.0s, max 180.0s
    assert durations[0] == 45.0
    assert durations[1] == 180.0

    # Verify explicit warnings were logged
    assert "raw duration (5.0s) is below minimum threshold" in caplog.text
    assert "raw duration (320.0s) exceeds maximum threshold" in caplog.text


def test_step2_chunk_boundary_safety(temp_metadata_dir):
    """
    Verify that clip start/end timestamps NEVER escape the enclosing chunk bounds (00:00:00 to 00:30:00).
    """
    outlines = [
        {"title": "Near End Clip", "subtopics": ["Close to border"], "chunk_index": 0},
    ]

    # Clip starting 8 seconds before chunk end (00:30:00 = 1800s)
    # LLM proposes 00:29:52 to 00:30:30 (exceeding chunk end 00:30:00)
    llm_simulated_response = json.dumps([
        {"id": "1", "outline": "Near End Clip", "start_time": "00:29:52,000", "end_time": "00:30:30,000", "content": ["Near boundary"]}
    ])

    extractor = TimelineExtractor(metadata_dir=temp_metadata_dir, category="default")
    extractor.llm_client.call_with_retry = MagicMock(return_value=llm_simulated_response)

    results = extractor.extract_timeline(outlines)

    tp = TextProcessor()
    end_sec = tp.time_to_seconds(results[0]['end_time'])
    chunk_end_sec = tp.time_to_seconds("00:30:00,000")

    assert end_sec <= chunk_end_sec


def test_step2_category_specific_limits(temp_metadata_dir):
    """
    Verify that category-specific bounds are applied:
    - 'speech' allows up to 480s (8m), so 420s (7m) is NOT clamped.
    - 'entertainment' caps at 90s, so 120s IS clamped to 90s.
    """
    tp = TextProcessor()
    
    # 1. Test SPEECH (max 480s / 8 min)
    speech_extractor = TimelineExtractor(metadata_dir=temp_metadata_dir, category="speech")
    speech_extractor.llm_client.call_with_retry = MagicMock(return_value=json.dumps([
        {"id": "1", "outline": "Keynote Speech", "start_time": "00:01:00,000", "end_time": "00:08:00,000", "content": ["Talk"]}
    ]))
    speech_res = speech_extractor.extract_timeline([
        {"title": "Keynote Speech", "subtopics": ["Talk"], "chunk_index": 0}
    ])
    speech_dur = tp.time_to_seconds(speech_res[0]['end_time']) - tp.time_to_seconds(speech_res[0]['start_time'])
    assert speech_dur == 420.0  # 7m00s preserved (< 480s)

    # 2. Test ENTERTAINMENT (max 90s)
    ent_extractor = TimelineExtractor(metadata_dir=temp_metadata_dir, category="entertainment")
    ent_extractor.llm_client.call_with_retry = MagicMock(return_value=json.dumps([
        {"id": "1", "outline": "Comedy Bit", "start_time": "00:01:00,000", "end_time": "00:03:00,000", "content": ["Joke"]}
    ]))
    ent_res = ent_extractor.extract_timeline([
        {"title": "Comedy Bit", "subtopics": ["Joke"], "chunk_index": 0}
    ])
    ent_dur = tp.time_to_seconds(ent_res[0]['end_time']) - tp.time_to_seconds(ent_res[0]['start_time'])
    assert ent_dur == 90.0  # 120s clamped to 90s


@pytest.mark.asyncio
async def test_step1_empty_fallback_tagging_and_warning(tmp_path):
    """
    Verify that when Step 1 produces no outlines, SimplePipelineAdapter generates
    structured fallback clips with is_fallback=True and tags=['fallback', 'auto_segmented'],
    and emits a visible warning to simple_progress.
    """
    from backend.services.simple_pipeline_adapter import SimplePipelineAdapter
    from backend.services.simple_progress import get_progress_snapshot

    project_id = "test-fallback-proj-123"
    adapter = SimplePipelineAdapter(project_id, "task-123")

    # Mock video info (500s video)
    mock_vinfo = {"format": {"duration": "500.0"}}
    
    with patch("backend.core.path_utils.get_project_directory", return_value=tmp_path), \
         patch("backend.services.simple_pipeline_adapter.run_step1_outline", return_value=[]), \
         patch("backend.services.simple_pipeline_adapter.run_step6_video", return_value=[]), \
         patch("backend.utils.video_processor.VideoProcessor") as mock_vp_cls:
        
        mock_vp = MagicMock()
        mock_vp.get_video_info.return_value = mock_vinfo
        mock_vp_cls.return_value = mock_vp

        result = await adapter.process_project_sync(
            input_video_path="/fake/input.mp4",
            input_srt_path=None
        )

    # Check titles output
    step4_file = tmp_path / "metadata" / "step4_titles.json"
    assert step4_file.exists()
    
    with open(step4_file, "r", encoding="utf-8") as f:
        clips = json.load(f)

    # For a 500s video (>90s), multiple fallback segments should be generated
    assert len(clips) > 1
    for clip in clips:
        assert clip.get("is_fallback") is True
        assert clip.get("fallback_reason") == "step1_outline_empty"
        assert "fallback" in clip.get("tags", [])
        assert "auto_segmented" in clip.get("tags", [])
        assert "Fallback highlight segment" in clip.get("recommend_reason", "")

    # Check progress snapshot
    snapshot = get_progress_snapshot(project_id)
    assert snapshot is not None
