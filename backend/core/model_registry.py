"""
Model Registry for AI Video Clipper
Maintains the verified 100%-quota model pool across providers and tiers.

Strict Constraints:
- Exhausted models ('qwen-flash-character', 'qwen-plus-character') are PERMANENTLY EXCLUDED.
- DeepSeek, Kimi, GLM, and Qwen models are confirmed accessible via Alibaba DashScope compatible mode.
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# List of permanently exhausted models that must NEVER appear in active pools
EXHAUSTED_MODELS = frozenset([
    "qwen-flash-character",
    "qwen-plus-character",
    "qwen-turbo-latest",
])

MODEL_REGISTRY: Dict[str, Dict[str, List[str]]] = {
    "qwen": {
        "flagship": [
            "qwen3.8-max",
            "qwen3.7-max",
            "qwen3.7-max-2026-06-08",
            "qwen3.6-max-preview",
            "qwen3-max",
            "qwen3-max-preview",
            "qwen3-235b-a22b",
            "qwen3.5-397b-a17b",
            "qwen-max",
            "qwq-plus",
        ],
        "plus": [
            "qwen3.7-plus",
            "qwen3.6-plus",
            "qwen3.5-plus",
            "qwen3.5-omni-plus",
            "qwen-plus",
            "qwen-plus-latest",
            "qwen3-coder-plus",
        ],
        "fast": [
            "qwen3.7-flash",
            "qwen3.6-flash",
            "qwen3.5-flash",
            "qwen3.5-omni-flash",
            "qwen-turbo",
            "qwen-flash",
            "qwen3-coder-flash",
        ],
        "reasoning": [
            "qwen3-235b-a22b-thinking-2507",
            "qwen3-30b-a3b-thinking-2507",
            "qwen3-next-80b-a3b-thinking",
            "qvq-max",
        ],
    },
    "deepseek": {
        "flagship": [
            "deepseek-v4-flash",
            "deepseek-v3.2",
            "deepseek-v4-pro",
        ],
        "fast": [
            "deepseek-v4-flash",
            "deepseek-v3.2",
        ],
    },
    "kimi": {
        "flagship": [
            "kimi-k2.7-code",
        ],
    },
    "glm": {
        "flagship": [
            "glm-5.2",
        ],
        "fast": [
            "glm-5.1",
        ],
    },
    "asr": {
        "realtime": [
            "fun-asr",
            "fun-asr-mtl",
            "fun-asr-2025-11-07",
            "qwen3-asr-flash",
        ],
        "file": [
            "qwen3-asr-flash-filetrans",
            "qwen3-asr-flash-filetrans-2025-11-17",
            "fun-asr-flash-2026-06-15",
        ],
    },
    "vl": {
        "flagship": [
            "qwen3-vl-plus",
            "qwen3-vl-235b-a22b-instruct",
            "qwen-vl-max",
            "qwen2.5-vl-72b-instruct",
        ],
        "fast": [
            "qwen3-vl-flash",
            "qwen-vl-plus",
        ],
    },
}

# Runtime validation to guarantee no exhausted models ever enter registry
for family, tiers in MODEL_REGISTRY.items():
    for tier, models in tiers.items():
        for m in models:
            if m in EXHAUSTED_MODELS:
                raise RuntimeError(f"Exhausted model {m} found in MODEL_REGISTRY {family}:{tier}!")


def get_models_by_family(family: str, tier: Optional[str] = None) -> List[str]:
    """Retrieve models for a specific family (and optional tier), excluding exhausted models."""
    fam_dict = MODEL_REGISTRY.get(family, {})
    if tier:
        return [m for m in fam_dict.get(tier, []) if m not in EXHAUSTED_MODELS]
    res = []
    for t, m_list in fam_dict.items():
        res.extend([m for m in m_list if m not in EXHAUSTED_MODELS])
    return res


def get_models_by_tier(tier_or_family: str, tier: Optional[str] = None) -> List[str]:
    """Retrieve models across all families (or specific family) for a given tier."""
    if tier is not None:
        return get_models_by_family(tier_or_family, tier)
    res = []
    for fam, fam_dict in MODEL_REGISTRY.items():
        if tier_or_family in fam_dict:
            res.extend([m for m in fam_dict[tier_or_family] if m not in EXHAUSTED_MODELS])
    return res


def get_flagship_families() -> List[str]:
    """Returns all families that have flagship tier models."""
    return [
        fam for fam, tiers in MODEL_REGISTRY.items()
        if "flagship" in tiers and any(m not in EXHAUSTED_MODELS for m in tiers["flagship"])
    ]
