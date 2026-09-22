"""
Unit tests for efficient multi-model ensembling redesign:
- Step 1: Sequential Critique prompt generation
- Step 3: Borderline-only second opinion split
- Step 3: Second opinion execution and bypass verification
"""
import pytest
from unittest.mock import MagicMock
from backend.core.shared_config import ENSEMBLE_BORDERLINE_MIN, ENSEMBLE_BORDERLINE_MAX
from backend.pipeline.step1_outline import OutlineExtractor
from backend.pipeline.step3_scoring import ClipScorer


def test_critique_prompt_generation():
    extractor = OutlineExtractor()
    candidates = [
        {"id": "1", "title": "Moment A", "topic": "Topic A", "start_anchor": "Hello", "end_anchor": "World"},
        {"id": "2", "title": "Moment B", "topic": "Topic B", "start_anchor": "Foo", "end_anchor": "Bar"}
    ]
    prompt = extractor._build_critique_prompt(candidates, category="ai_moment")
    assert "PRUNE" in prompt
    assert "ADD" in prompt
    assert "Moment A" in prompt
    assert "ai_moment" in prompt


def test_borderline_scoring_split():
    clips = [
        {"id": "1", "score": 0.95},  # Clear winner -> no 2nd opinion
        {"id": "2", "score": 0.70},  # Borderline -> needs 2nd opinion
        {"id": "3", "score": 0.58},  # Borderline -> needs 2nd opinion
        {"id": "4", "score": 0.35},  # Clear reject -> no 2nd opinion
    ]
    borderline = [c for c in clips if ENSEMBLE_BORDERLINE_MIN <= c["score"] <= ENSEMBLE_BORDERLINE_MAX]
    clear = [c for c in clips if c not in borderline]
    assert len(borderline) == 2
    assert [c["id"] for c in borderline] == ["2", "3"]
    assert len(clear) == 2
    assert [c["id"] for c in clear] == ["1", "4"]


def test_step3_second_opinion_bypassed_for_clear_winner(monkeypatch):
    """Verify Model 2 is completely bypassed when all clips are clear winners (>0.82)."""
    scorer = ClipScorer(category="tech_take")
    clips = [
        {
            "id": "1",
            "outline": "Clear Winner Tech Clip",
            "content": ["Revolutionary chip architecture"],
            "start_time": "00:01:00,000",
            "end_time": "00:02:00,000",
            "category": "tech_take"
        }
    ]

    mock_m2_called = False

    def mock_query(self, input_for_llm, model_name):
        nonlocal mock_m2_called
        if "qwen" in model_name:
            return [{"final_score": 0.95, "recommend_reason": "Extraordinary insight", "what_makes_this_distinctive": "First principle explanation"}]
        else:
            mock_m2_called = True
            return [{"final_score": 0.90, "recommend_reason": "Great", "what_makes_this_distinctive": "Good"}]

    monkeypatch.setattr(ClipScorer, "_query_model_scoring", mock_query)

    scored = scorer._get_llm_evaluation(clips)
    assert len(scored) == 1
    assert scored[0]["scored_by"] == "one_model"
    assert len(scored[0]["models_evaluated"]) == 1
    assert mock_m2_called is False  # Model 2 was bypassed!
