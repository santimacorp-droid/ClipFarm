"""
Tests for Phase 2: Ensembling in Step 1 (3-model overlap deduplication & confidence tagging)
and Step 3 (2-model score averaging & score disagreement flag).
"""

import pytest
import logging
from backend.pipeline.step1_outline import OutlineExtractor
from backend.pipeline.step3_scoring import ClipScorer


def test_step1_ensemble_deduplication_and_confidence(tmp_path):
    """Verify Step 1 merges >=50% overlapping moments, sets high/low confidence, and retains descriptive title."""
    extractor = OutlineExtractor(metadata_dir=tmp_path)

    # Simulated candidate outputs from 3 models
    candidates = [
        # Model 1 (Qwen) extracts moment at 01:00 - 03:00
        {
            "title": "AI Agents Short Title",
            "start_time": "00:01:00,000",
            "end_time": "00:03:00,000",
            "chunk_index": 0,
            "subtopics": ["Agent autonomous behavior"],
            "source_model": "qwen3.7-max"
        },
        # Model 2 (DeepSeek) extracts substantially overlapping moment (>= 50% overlap) with more descriptive title
        {
            "title": "Autonomous AI Agents Reshaping Engineering Workflows",
            "start_time": "00:01:15,000",
            "end_time": "00:03:10,000",
            "chunk_index": 0,
            "subtopics": ["Multi-agent team coordination", "Coding assistants"],
            "source_model": "deepseek-v4-pro"
        },
        # Model 3 (GLM) extracts an isolated, unique moment at 05:00 - 07:00
        {
            "title": "Quantum Computing Breakthrough in Material Science",
            "start_time": "00:05:00,000",
            "end_time": "00:07:00,000",
            "chunk_index": 0,
            "subtopics": ["Superconducting qubits"],
            "source_model": "glm-5.2"
        }
    ]

    final_moments = extractor._ensemble_and_deduplicate_moments(candidates)

    # Moments 1 and 2 should be merged into one high-confidence moment
    # Moment 3 should remain separate as low-confidence
    assert len(final_moments) == 2

    # Verify merged moment
    ai_moment = next(m for m in final_moments if "Autonomous AI Agents" in m["title"])
    assert ai_moment["confidence"] == "high"
    assert ai_moment["models_count"] == 2
    assert set(ai_moment["models_found"]) == {"qwen3.7-max", "deepseek-v4-pro"}
    # More descriptive title retained
    assert ai_moment["title"] == "Autonomous AI Agents Reshaping Engineering Workflows"
    # Subtopics merged
    assert "Agent autonomous behavior" in ai_moment["subtopics"]
    assert "Multi-agent team coordination" in ai_moment["subtopics"]

    # Verify isolated moment
    quantum_moment = next(m for m in final_moments if "Quantum" in m["title"])
    assert quantum_moment["confidence"] == "low"
    assert quantum_moment["models_count"] == 1
    assert quantum_moment["models_found"] == ["glm-5.2"]


def test_step1_duplicate_guard(tmp_path, caplog):
    """Verify duplicate guard drops any residual moment overlapping >50%."""
    extractor = OutlineExtractor(metadata_dir=tmp_path)

    # Force two overlapping items where one is low confidence and one is high confidence
    candidates = [
        {
            "title": "High Confidence Clip",
            "start_time": "00:01:00,000",
            "end_time": "00:03:00,000",
            "chunk_index": 0,
            "source_model": "qwen3.7-max",
            "models_found": {"qwen3.7-max", "deepseek-v4-pro"},
            "confidence": "high"
        },
        {
            "title": "Low Confidence Duplicate",
            "start_time": "00:01:10,000",
            "end_time": "00:02:50,000",  # Heavily overlaps with clip 1 (>80%)
            "chunk_index": 0,
            "source_model": "glm-5.2",
            "models_found": {"glm-5.2"},
            "confidence": "low"
        }
    ]

    with caplog.at_level(logging.WARNING):
        guarded = extractor._apply_duplicate_guard(candidates)

    # Should only keep 1 item
    assert len(guarded) == 1
    assert guarded[0]["title"] == "High Confidence Clip"
    assert "Duplicate guard triggered" in caplog.text


def test_step3_ensemble_score_averaging_and_disagreement(tmp_path, monkeypatch):
    """Verify Step 3 averages scores from 2 models and flags score_disagreement when diff > 0.30."""
    scorer = ClipScorer(category="story")

    clips = [
        {
            "id": "1",
            "outline": "Viral Breakthrough Moment",
            "content": ["Fascinating discussion on future AI"],
            "start_time": "00:01:00,000",
            "end_time": "00:03:30,000",  # 150s (well within story window 90-300s)
            "category": "story"
        },
        {
            "id": "2",
            "outline": "Controversial Edge Case Discussion",
            "content": ["Polarizing debate"],
            "start_time": "00:04:00,000",
            "end_time": "00:06:00,000",  # 120s
            "category": "story"
        }
    ]

    # Mock _query_model_scoring for Model 1 (Qwen) and Model 2 (DeepSeek)
    def mock_query(self, input_for_llm, model_name):
        if "qwen" in model_name:
            return [
                {"final_score": 0.80, "recommend_reason": "High virality hook", "what_makes_this_distinctive": "Clear payoff"},
                {"final_score": 0.75, "recommend_reason": "Strong tension", "what_makes_this_distinctive": "High conflict"}
            ]
        else:
            # DeepSeek agrees on clip 1 (0.76 vs 0.80, diff 0.04 <= 0.30)
            # but strongly disagrees on clip 2 (0.35 vs 0.75, diff 0.40 > 0.30)
            return [
                {"final_score": 0.76, "recommend_reason": "Excellent narrative arc", "what_makes_this_distinctive": "Dynamic pace"},
                {"final_score": 0.35, "recommend_reason": "Niche topic, low interest", "what_makes_this_distinctive": "Too specialized"}
            ]

    monkeypatch.setattr(ClipScorer, "_query_model_scoring", mock_query)

    scored_clips = scorer._get_llm_evaluation(clips)

    assert len(scored_clips) == 2

    # Clip 1: Agreement (diff 0.04 <= 0.30)
    clip_1 = scored_clips[0]
    assert clip_1["score_disagreement"] is False
    # Raw average = (0.80 + 0.76) / 2 = 0.78
    # Duration appropriateness for 150s in story [90, 300] = 1.0
    # Blended = 0.80 * 0.78 + 0.20 * 1.0 = 0.624 + 0.20 = 0.824 -> round(0.82)
    assert 0.81 <= clip_1["final_score"] <= 0.83

    # Clip 2: Disagreement (diff = |0.75 - 0.35| = 0.40 > 0.30)
    clip_2 = scored_clips[1]
    assert clip_2["score_disagreement"] is True
    # Raw average = (0.75 + 0.35) / 2 = 0.55
    # Blended = 0.80 * 0.55 + 0.20 * 1.0 = 0.44 + 0.20 = 0.64
    assert 0.63 <= clip_2["final_score"] <= 0.65
