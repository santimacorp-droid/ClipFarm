import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.pipeline.step2_timeline import TimelineExtractor, run_step2_timeline


def test_split_srt_into_subchunks_respects_max_chars(tmp_path):
    extractor = TimelineExtractor(metadata_dir=tmp_path)

    # Generate 100 SRT entries, each ~100 characters
    srt_entries = []
    for i in range(100):
        start_s = i * 5
        end_s = (i + 1) * 5
        srt_entries.append({
            "index": i + 1,
            "start_time": f"00:{start_s//60:02d}:{start_s%60:02d},000",
            "end_time": f"00:{end_s//60:02d}:{end_s%60:02d},000",
            "text": f"This is sentence number {i} with some descriptive dialogue words."
        })

    # Total chars would be ~10,000. With max_chars=3000, should create ~4-5 subchunks.
    subchunks = extractor._split_srt_into_subchunks(srt_entries, max_chars=3000, overlap_entries=5)

    assert len(subchunks) >= 3
    for sc in subchunks:
        sc_text = "".join(f"{s['index']}\n{s['start_time']} --> {s['end_time']}\n{s['text']}\n\n" for s in sc)
        # Each subchunk's text must respect max_chars (or be bounded tightly)
        assert len(sc_text) <= 3500


def test_deduplicate_and_merge_overlapping_items(tmp_path):
    extractor = TimelineExtractor(metadata_dir=tmp_path)

    items = [
        {
            "id": "1",
            "outline": "Overcoming Adversity",
            "start_time": "00:01:00,000",
            "end_time": "00:02:10,000",
            "content": ["Part 1 of the story"]
        },
        {
            "id": "2",
            "outline": "Overcoming Adversity",
            "start_time": "00:02:05,000",
            "end_time": "00:03:00,000",
            "content": ["Part 2 of the story"]
        },
        {
            "id": "3",
            "outline": "Different Topic Later",
            "start_time": "00:08:00,000",
            "end_time": "00:09:00,000",
            "content": ["Completely separate section"]
        }
    ]

    merged = extractor._deduplicate_and_merge_items(items)
    assert len(merged) == 2

    adversity_item = next(m for m in merged if "Adversity" in m["outline"])
    # Boundaries merged: 00:01:00 to 00:03:00
    assert "00:01:00" in adversity_item["start_time"]
    assert "00:03:00" in adversity_item["end_time"]
    assert len(adversity_item["content"]) == 2


def test_step2_loud_failure_when_llm_fails(tmp_path):
    """
    Verify that Step 2 raises a clear RuntimeError rather than silently producing
    empty output if the LLM permanently fails.
    """
    extractor = TimelineExtractor(metadata_dir=tmp_path)
    extractor.srt_chunks_dir.mkdir(parents=True, exist_ok=True)

    chunk_0_file = extractor.srt_chunks_dir / "chunk_0.json"
    chunk_0_file.write_text(json.dumps([
        {"index": 1, "start_time": "00:00:00,000", "end_time": "00:01:00,000", "text": "Testing speech"}
    ]), encoding="utf-8")

    outlines = [{"chunk_index": 0, "title": "Test Topic", "subtopics": ["Subtopic 1"]}]

    # Force LLM client call to fail permanently
    extractor.llm_client.call_with_retry = MagicMock(side_effect=RuntimeError("DashScope 400 Context Overflow"))

    with pytest.raises(RuntimeError) as exc_info:
        extractor.extract_timeline(outlines)

    assert "Step 2 timeline extraction failed" in str(exc_info.value)


def test_repair_short_clip_boundary_via_llm(tmp_path):
    extractor = TimelineExtractor(metadata_dir=tmp_path)
    srt_data = [
        {"index": 1, "start_time": "00:00:10,000", "end_time": "00:00:12,000", "text": "I was beat as a child."},
        {"index": 2, "start_time": "00:00:12,500", "end_time": "00:00:25,000", "text": "My mother was crazy."},
        {"index": 3, "start_time": "00:00:25,500", "end_time": "00:00:45,000", "text": "And that is how I found my true strength."}
    ]

    item = {"outline": "Overcoming Trauma", "content": ["Turning scars into strength"]}
    
    # Simulate LLM repair returning resolution at 45 seconds
    extractor.llm_client.call_with_retry = MagicMock(return_value=json.dumps({
        "end_time": "00:00:45,000",
        "resolution_found": True
    }))

    repaired_end = extractor._repair_short_clip_boundary(
        timeline_item=item,
        start_sec=10.0,
        raw_end_sec=12.0,
        chunk_end_sec=1800.0,
        srt_data=srt_data,
        min_dur=15.0,
        max_dur=240.0
    )

    assert repaired_end == 45.0
    assert item.get("needs_review") is not True


def test_sentence_aligned_fallback_when_no_llm_resolution(tmp_path):
    extractor = TimelineExtractor(metadata_dir=tmp_path)
    srt_data = [
        {"index": 1, "start_time": "00:00:10,000", "end_time": "00:00:13,000", "text": "Short snippet"},
        {"index": 2, "start_time": "00:00:13,500", "end_time": "00:00:22,000", "text": "Middle filler text"},
        {"index": 3, "start_time": "00:00:22,500", "end_time": "00:00:27,000", "text": "And the thought resolves here."},
        {"index": 4, "start_time": "00:00:27,500", "end_time": "00:00:35,000", "text": "Unrelated next point."}
    ]

    item = {"outline": "Snippet", "content": ["Test"]}

    # LLM repair fails
    extractor.llm_client.call_with_retry = MagicMock(side_effect=Exception("API failure"))

    # start_sec = 10.0, min_dur = 15.0 -> min target = 25.0s
    # Cue 3 ends at 27.0s with '.'
    repaired_end = extractor._repair_short_clip_boundary(
        timeline_item=item,
        start_sec=10.0,
        raw_end_sec=13.0,
        chunk_end_sec=1800.0,
        srt_data=srt_data,
        min_dur=15.0,
        max_dur=240.0
    )

    # Must snap to Cue 3's sentence end (27.0 + 0.12 = 27.12), NOT blind 25.0s!
    assert abs(repaired_end - 27.12) < 0.01
