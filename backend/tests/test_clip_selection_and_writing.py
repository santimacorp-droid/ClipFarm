import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.pipeline.step3_scoring import ClipScorer
from backend.pipeline.step4_title import TitleGenerator, run_step4_title
from backend.utils.hook_generator import ViralHookGenerator
from backend.core.shared_config import get_prompt_files


def test_step3_distinctiveness_parsing_and_downstream_merging():
    """
    Verify that Step 3 extracts 'what_makes_this_distinctive' before scoring,
    and merges it cleanly into 'recommend_reason' for downstream consumers.
    """
    clips = [
        {
            "id": "1",
            "chunk_index": 0,
            "outline": "Happiness Equation",
            "content": ["Satisfaction vs ambition", "The dopamine crash"],
            "start_time": "00:01:00,000",
            "end_time": "00:02:30,000"
        }
    ]

    llm_simulated_response = json.dumps([
        {
            "outline": "Happiness Equation",
            "content": ["Satisfaction vs ambition", "The dopamine crash"],
            "start_time": "00:01:00,000",
            "end_time": "00:02:30,000",
            "what_makes_this_distinctive": "The speaker admits reaching his net worth goal immediately triggered depression because the dopamine chase collapsed.",
            "final_score": 0.92,
            "recommend_reason": "Brutally honest founder admission exposing the psychological hollow at the peak of success."
        }
    ])

    scorer = ClipScorer()
    scorer.llm_client.call_with_retry = MagicMock(return_value=llm_simulated_response)

    scored = scorer.score_clips(clips)

    assert len(scored) == 1
    clip = scored[0]
    assert clip["final_score"] in (0.92, 0.94)
    assert clip["what_makes_this_distinctive"] == "The speaker admits reaching his net worth goal immediately triggered depression because the dopamine chase collapsed."
    # Both distinctive admission and recommendation rationale are preserved for downstream
    assert "dopamine chase collapsed" in clip["recommend_reason"]
    assert "Brutally honest founder admission" in clip["recommend_reason"]


def test_step3_robustness_when_distinctiveness_omitted():
    """
    Verify that if the LLM omits 'what_makes_this_distinctive',
    ClipScorer still scores and extracts recommend_reason without crashing.
    """
    clips = [
        {
            "id": "1",
            "chunk_index": 0,
            "outline": "Startup Advice",
            "content": ["Hiring fast", "Firing faster"],
            "start_time": "00:01:00,000",
            "end_time": "00:02:00,000"
        }
    ]

    llm_simulated_response = json.dumps([
        {
            "outline": "Startup Advice",
            "start_time": "00:01:00,000",
            "end_time": "00:02:00,000",
            "final_score": 0.86,
            "recommend_reason": "High-stakes advice on organizational velocity."
        }
    ])

    scorer = ClipScorer()
    scorer.llm_client.call_with_retry = MagicMock(return_value=llm_simulated_response)

    scored = scorer.score_clips(clips)
    assert scored[0]["final_score"] in (0.86, 0.89)
    assert scored[0]["recommend_reason"] == "High-stakes advice on organizational velocity."


def test_step4_receives_distinctiveness_context(tmp_path):
    """
    Verify that TitleGenerator packages recommend_reason and what_makes_this_distinctive
    into the LLM input payload so titles are grounded in why the clip scored well.
    """
    generator = TitleGenerator(metadata_dir=tmp_path)
    captured_payload = []

    def fake_call(prompt, payload, **kwargs):
        if isinstance(payload, list):
            captured_payload.extend(payload)
        return json.dumps({"1": "The Day I Realized Money Solved Nothing"})

    generator.llm_client.call_with_retry = fake_call

    scored_clips = [
        {
            "id": "1",
            "chunk_index": 0,
            "outline": "The Science of Wealth",
            "content": ["Net worth milestones", "Depression after exit"],
            "recommend_reason": "The speaker admits reaching his net worth goal triggered depression.",
            "what_makes_this_distinctive": "The speaker admits reaching his net worth goal triggered depression."
        }
    ]

    titled = generator.generate_titles(scored_clips)

    assert len(captured_payload) == 1
    item = captured_payload[0]
    assert item["id"] == "1"
    assert "depression" in item["recommend_reason"]
    assert "depression" in item["what_makes_this_distinctive"]
    assert titled[0]["generated_title"] == "The Day I Realized Money Solved Nothing"


def test_hook_generator_receives_distinctiveness_context():
    """
    Verify that ViralHookGenerator receives distinctiveness context and avoids generic tropes.
    """
    clips_data = [
        {
            "id": "1",
            "title": "Founder Burnout",
            "recommend_reason": "Founder candidly admits selling company for $20M felt like a funeral.",
            "content": ["I sold my company and stared at the ceiling for 6 months crying."]
        }
    ]

    captured_input = []
    def fake_batch_call(prompt, items):
        captured_input.extend(items)
        return json.dumps([
            {
                "id": "1",
                "hook_headline": "Selling My Company Felt Like A Funeral 📈💡",
                "clip_title": "The $20M Exit That Broke Me"
            }
        ])

    with patch("backend.utils.hook_generator.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.call_with_retry = fake_batch_call
        mock_client.parse_json_response = json.loads
        mock_client_cls.return_value = mock_client

        hooks = ViralHookGenerator.batch_generate_hooks(clips_data, video_title="Podcast Episode 42")

    assert len(captured_input) == 1
    inp = captured_input[0]
    assert "felt like a funeral" in inp["distinctive_reason"]
    assert hooks["1"]["hook_headline"] == "Selling My Company Felt Like A Funeral 📈💡"


def test_step4_generates_both_title_and_hook_text(tmp_path):
    """
    Verify that TitleGenerator parses LLM response with both 'title' and 'hook',
    populates 'generated_title' (4-9 words), 'hook_text' (3-6 words), and 'hook_title'.
    """
    generator = TitleGenerator(metadata_dir=tmp_path)

    fake_response = json.dumps({
        "1": {
            "title": "The $20M Exit That Broke My Soul",
            "hook": "Selling My Company Broke Me"
        }
    })
    generator.llm_client.call_with_retry = MagicMock(return_value=fake_response)

    scored_clips = [
        {
            "id": "1",
            "chunk_index": 0,
            "outline": "Founder Exit Story",
            "content": ["I sold my company and broke down"],
            "recommend_reason": "Honest founder story",
            "what_makes_this_distinctive": "Raw emotional admission"
        }
    ]

    titled = generator.generate_titles(scored_clips)

    assert len(titled) == 1
    clip = titled[0]
    assert clip["generated_title"] == "The $20M Exit That Broke My Soul"
    assert "Selling My Company Broke Me" in clip["hook_text"]
    assert clip["hook_title"] == clip["hook_text"]

    title_words = clip["generated_title"].split()
    assert 4 <= len(title_words) <= 9

    hook_words = clip["hook_text"].split()
    assert 3 <= len(hook_words) <= 8


def test_step4_hook_text_fallback_to_five_words(tmp_path):
    """
    Verify that if the LLM response returns a plain string or omits 'hook',
    hook_text falls back to the first 5 words of generated_title.
    """
    generator = TitleGenerator(metadata_dir=tmp_path)

    # Legacy / string response
    fake_response_str = json.dumps({
        "1": "Why Most Founders Fail Within Three Years"
    })
    generator.llm_client.call_with_retry = MagicMock(return_value=fake_response_str)

    scored_clips = [
        {
            "id": "1",
            "chunk_index": 0,
            "outline": "Startup Failure",
            "content": ["Founders run out of cash"]
        }
    ]

    titled = generator.generate_titles(scored_clips)
    clip = titled[0]
    assert clip["generated_title"] == "Why Most Founders Fail Within Three Years"
    # Fallback to first 5 words
    assert "Why Most Founders Fail Within" in clip["hook_text"]
    assert clip["hook_title"] == clip["hook_text"]


def test_step4_run_pipeline_produces_titles_json(tmp_path):
    """
    Verify that run_step4_title writes step4_titles.json with generated_title and hook_text.
    """
    input_file = tmp_path / "step3_scored.json"
    output_file = tmp_path / "step4_titles.json"

    clips_data = [
        {
            "id": "1",
            "chunk_index": 0,
            "outline": "AI Future",
            "content": ["AI will transform coding completely"],
            "recommend_reason": "Clear prediction about software engineering",
            "what_makes_this_distinctive": "Coding workflow shifts"
        }
    ]
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(clips_data, f)

    fake_response = json.dumps({
        "1": {
            "title": "How AI Changes Software Engineering Forever",
            "hook": "AI Changes Coding Forever"
        }
    })

    with patch("backend.pipeline.step4_title.LLMClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.call_with_retry = MagicMock(return_value=fake_response)
        mock_client.parse_json_response = json.loads
        mock_client_cls.return_value = mock_client

        res = run_step4_title(
            high_score_clips_path=input_file,
            metadata_dir=tmp_path,
            output_path=output_file
        )

    assert output_file.exists()
    with open(output_file, "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert len(saved) == 1
    assert saved[0]["generated_title"] == "How AI Changes Software Engineering Forever"
    assert "AI Changes Coding Forever" in saved[0]["hook_text"]
    assert saved[0]["hook_title"] == saved[0]["hook_text"]

