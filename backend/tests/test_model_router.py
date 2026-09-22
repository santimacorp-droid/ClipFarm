"""
Tests for Phase 2: Model Registry and Multi-Model Router
"""

import pytest
from backend.core.model_registry import MODEL_REGISTRY, EXHAUSTED_MODELS, get_models_by_family, get_models_by_tier
from backend.core.model_router import ModelRouter, model_router


def test_registry_excludes_exhausted_models():
    """Verify exhausted models are completely excluded from the registry."""
    assert "qwen-flash-character" in EXHAUSTED_MODELS
    assert "qwen-plus-character" in EXHAUSTED_MODELS

    # Search through every family and tier in registry
    all_registered_models = []
    for family, tiers in MODEL_REGISTRY.items():
        for tier, models in tiers.items():
            all_registered_models.extend(models)

    for exhausted in EXHAUSTED_MODELS:
        assert exhausted not in all_registered_models, f"{exhausted} must never appear in registry"


def test_registry_structure_and_helper_functions():
    """Verify registry categories and retrieval helpers."""
    qwen_flagships = get_models_by_family("qwen", "flagship")
    assert len(qwen_flagships) > 0
    assert "qwen3.8-max" in qwen_flagships or "qwen-max" in qwen_flagships

    deepseek_models = get_models_by_family("deepseek", "flagship")
    assert "deepseek-v4-pro" in deepseek_models

    glm_models = get_models_by_family("glm", "flagship")
    assert "glm-5.2" in glm_models

    kimi_models = get_models_by_family("kimi", "flagship")
    assert "kimi-k2.7-code" in kimi_models

    all_fast = get_models_by_tier("fast")
    assert len(all_fast) > 0


def test_model_router_cross_family_flagship_rotation():
    """Verify moment_extraction and scoring rotate across distinct families."""
    router = ModelRouter()

    # Call 4 times for moment_extraction: should cycle through distinct families
    selected_models = [router.next("moment_extraction") for _ in range(4)]
    
    # Check that at least 3 distinct families are represented in 4 consecutive calls
    families_represented = set()
    for m in selected_models:
        if m.startswith("qwen") or m.startswith("qwq"):
            families_represented.add("qwen")
        elif m.startswith("deepseek"):
            families_represented.add("deepseek")
        elif m.startswith("glm"):
            families_represented.add("glm")
        elif m.startswith("kimi"):
            families_represented.add("kimi")

    assert len(families_represented) >= 3, f"Expected rotation across families, got {families_represented}"


def test_model_router_titling_stays_in_fast_tier():
    """Verify titling task stays strictly within fast tier."""
    router = ModelRouter()

    fast_models = set(get_models_by_family("qwen", "fast"))
    for _ in range(10):
        model = router.next("titling")
        assert model in fast_models, f"Titling picked non-fast model: {model}"


def test_model_router_ensemble_models_cross_family():
    """Verify get_ensemble_models returns models from distinct families."""
    router = ModelRouter()
    ensemble_3 = router.get_ensemble_models("moment_extraction", count=3)
    assert len(ensemble_3) == 3

    families = []
    for m in ensemble_3:
        if m.startswith("qwen") or m.startswith("qwq"):
            families.append("qwen")
        elif m.startswith("deepseek"):
            families.append("deepseek")
        elif m.startswith("glm"):
            families.append("glm")
        elif m.startswith("kimi"):
            families.append("kimi")

    assert len(set(families)) == 3, f"Expected 3 distinct families, got {families}"


def test_model_router_call_with_fallback():
    """Verify call_with_fallback catches errors on primary model and falls back to second."""
    router = ModelRouter()

    attempt_log = []

    def failing_fn(model_name: str) -> str:
        attempt_log.append(model_name)
        if len(attempt_log) == 1:
            raise RuntimeError("API Rate Limit 429 on primary model")
        return f"Success with {model_name}"

    result = router.call_with_fallback("scoring", failing_fn, max_retries=2)
    assert len(attempt_log) == 2
    assert attempt_log[0] != attempt_log[1]  # Switched to different model
    assert "Success with" in result
