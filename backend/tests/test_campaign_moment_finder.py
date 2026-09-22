"""Tests for campaign moment finder."""
import pytest
from backend.campaign.moment_finder import find_moments_in_transcript, _fuzzy_find_start_line

SAMPLE_SEGMENTS = [
    {"start": 0.0,  "end": 3.0,  "text": "There are normal fungus in your scalp."},
    {"start": 3.0,  "end": 8.0,  "text": "Think of your fungus and your bacteria as ants."},
    {"start": 8.0,  "end": 12.0, "text": "They eat the cookie crumbs on your skin."},
    {"start": 12.0, "end": 18.0, "text": "Horseshoe acne affects athletes who wear helmets."},
    {"start": 18.0, "end": 25.0, "text": "In my 43 years of clinical practice I have seen this."},
]

@pytest.fixture(autouse=True)
def mock_llm_client(monkeypatch):
    def fake_call(self, prompt, system_prompt=None, task=None):
        if "end_offset_seconds" in prompt:
            return '{"end_offset_seconds": 25.0}'
        if "JSON array of objects" in prompt:
            return '[{"moment_name": "Ants & Bacteria", "start_sec": 3.0, "end_sec": 35.0, "description": "Fungus analogy"}]'
        return '{"start_sec": 3.0, "end_sec": 35.0}'

    monkeypatch.setattr("backend.utils.llm_client.LLMClient.call_with_retry", fake_call)


def test_fuzzy_find_start_line():
    result = _fuzzy_find_start_line(
        SAMPLE_SEGMENTS,
        start_line="Think of your fungus and your bacteria as ants",
        duration_min=15,
        duration_max=40
    )
    assert result is not None
    assert abs(result['start_sec'] - 3.0) < 1.0  # found near 3s

def test_find_moments_high_confidence():
    moments = [{"name": "ant cookie", "start_line": "Think of your fungus and your bacteria as ants."}]
    results = find_moments_in_transcript(SAMPLE_SEGMENTS, moments, 15, 40)
    assert len(results) == 1
    assert results[0]['confidence'] == 'high'
    assert results[0]['start_sec'] < 10.0

MULTI_SEGMENTS = [
    {"start": 0.0,  "end": 2.5,  "text": "Welcome back everyone."},
    {"start": 2.5,  "end": 5.0,  "text": "Think of your fungus"},
    {"start": 5.0,  "end": 8.0,  "text": "and your bacteria"},
    {"start": 8.0,  "end": 11.5, "text": "as ants crawling around."},
    {"start": 11.5, "end": 15.0, "text": "They eat the cookie crumbs on your skin."},
    {"start": 15.0, "end": 22.0, "text": "And that is why your microbiome matters."},
    {"start": 22.0, "end": 30.0, "text": "Now let us talk about treatment options."},
    {"start": 30.0, "end": 65.0, "text": "This conclusion finishes the entire segment."},
]

def test_multi_segment_phrase_match():
    # Phrase spans across segment 1, 2, and 3
    result = _fuzzy_find_start_line(
        MULTI_SEGMENTS,
        start_line="Think of your fungus and your bacteria as ants",
        duration_min=15,
        duration_max=30
    )
    assert result is not None
    assert abs(result['start_sec'] - 2.5) < 0.5
    duration = result['end_sec'] - result['start_sec']
    assert 15.0 <= duration <= 30.0

def test_duration_clamping():
    moments = [{"name": "microbiome", "start_line": "Think of your fungus and your bacteria as ants"}]
    results = find_moments_in_transcript(MULTI_SEGMENTS, moments, duration_min=20, duration_max=35)
    assert len(results) == 1
    clip = results[0]
    duration = clip['end_sec'] - clip['start_sec']
    assert 20.0 <= duration <= 35.0


def test_snap_to_segment_end():
    from backend.campaign.moment_finder import _snap_to_segment_end
    # Segment ends are: 2.5, 5.0, 8.0, 11.5, 15.0, 22.0, 30.0, 65.0
    # Target 14.2 should snap to 15.0 (dist 0.8 <= 3.0)
    assert _snap_to_segment_end(MULTI_SEGMENTS, 14.2, tolerance=3.0) == 15.0
    # Target 21.8 should snap to 22.0 (dist 0.2 <= 3.0)
    assert _snap_to_segment_end(MULTI_SEGMENTS, 21.8, tolerance=3.0) == 22.0
    # Target 45.0 has nearest ends 30.0 (dist 15) and 65.0 (dist 20) -> exceeds tolerance, returns original
    assert _snap_to_segment_end(MULTI_SEGMENTS, 45.0, tolerance=3.0) == 45.0


def test_find_thought_end_bounds_and_fallback():
    from backend.campaign.moment_finder import find_thought_end
    # Test that find_thought_end returns within [start_sec + duration_min, start_sec + duration_max]
    start_sec = 2.5
    duration_min = 10.0
    duration_max = 25.0
    end_sec = find_thought_end(
        segments=MULTI_SEGMENTS,
        start_sec=start_sec,
        moment_name="Ants and bacteria",
        description="Explaining how bacteria and fungus interact",
        duration_min=duration_min,
        duration_max=duration_max
    )
    assert start_sec + duration_min <= end_sec <= start_sec + duration_max
    duration = end_sec - start_sec
    assert 10.0 <= duration <= 25.0


def test_auto_discover_moments_short_video():
    from backend.campaign.moment_finder import auto_discover_moments
    results = auto_discover_moments(
        segments=SAMPLE_SEGMENTS,
        total_duration=50.0,
        duration_min=20.0,
        duration_max=90.0
    )
    assert len(results) == 1
    assert results[0]["start_sec"] == 0.0
    assert results[0]["end_sec"] == 50.0


def test_auto_discover_moments_long_video():
    from backend.campaign.moment_finder import auto_discover_moments
    # 900 seconds video (15 minutes) with sample segments spaced out
    long_segments = [
        {"start": float(i * 10), "end": float(i * 10 + 8), "text": f"This is sentence number {i} talking about topic {i//5}."}
        for i in range(90)
    ]
    results = auto_discover_moments(
        segments=long_segments,
        total_duration=900.0,
        duration_min=30.0,
        duration_max=90.0
    )
    # Should discover multiple moments across the 900s footage
    assert len(results) >= 4
    for r in results:
        dur = r["end_sec"] - r["start_sec"]
        assert 25.0 <= dur <= 95.0
        assert 0.0 <= r["start_sec"] <= 900.0
        assert r["end_sec"] <= 900.0

    # Ensure moments are spread out across the video
    starts = [r["start_sec"] for r in results]
    assert min(starts) < 150.0
    assert max(starts) > 500.0


def test_auto_discover_moments_respects_max_clips():
    from backend.campaign.moment_finder import auto_discover_moments
    long_segments = [
        {"start": float(i * 15), "end": float(i * 15 + 10), "text": f"Segment {i}"}
        for i in range(40)
    ]
    results = auto_discover_moments(
        segments=long_segments,
        total_duration=600.0,
        duration_min=25.0,
        duration_max=60.0,
        max_clips=2
    )
    assert len(results) == 2


