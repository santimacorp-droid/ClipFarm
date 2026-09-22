"""
Model Router for AI Video Clipper
Manages cross-family rotation for quality-critical tasks, fast tier cycling for mechanical tasks,
and transparent fallback across models upon error.
"""

import logging
from typing import Dict, List, Optional, Callable, TypeVar, Any
from .model_registry import MODEL_REGISTRY, EXHAUSTED_MODELS, get_models_by_tier

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Ordered flagship families for cross-family rotation:
# Qwen -> DeepSeek -> GLM -> Kimi -> Qwen...
FLAGSHIP_FAMILY_ORDER = ["qwen", "deepseek", "glm", "kimi"]


class ModelRouter:
    """
    Intelligent Model Router.
    Routes tasks to optimal models:
    - moment_extraction & scoring: cycles flagship models across families (Qwen -> DeepSeek -> GLM -> Kimi).
    - titling: cycles fast models within Qwen.
    - Provides automatic failover to the next candidate model if a call fails.
    """

    def __init__(self):
        # Index tracking family cycle for quality-critical tasks
        self._flagship_family_idx: int = 0
        
        # Per-family flagship model indices (within each family)
        self._family_model_indices: Dict[str, int] = {
            fam: 0 for fam in FLAGSHIP_FAMILY_ORDER
        }

        # Index tracking Qwen fast tier for mechanical tasks
        self._qwen_fast_idx: int = 0

        # General task rotation index
        self._generic_indices: Dict[str, int] = {}

    def next(self, task: str = "general") -> str:
        """
        Returns the next model for the given task.
        - 'moment_extraction' / 'outline': rotates flagship across families.
        - 'scoring' / 'evaluation': rotates flagship across families.
        - 'titling' / 'metadata': rotates within Qwen fast tier.
        - other: rotates across Qwen plus / fast.
        """
        task_norm = task.lower().strip()

        if task_norm in ("moment_extraction", "outline", "step1", "scoring", "evaluation", "step3"):
            return self._next_cross_family_flagship()
        elif task_norm in ("titling", "metadata", "step4", "fast"):
            return self._next_qwen_fast()
        elif task_norm in ("clustering", "step5"):
            return self._next_qwen_plus()
        else:
            return self._next_qwen_fast()

    def _next_cross_family_flagship(self) -> str:
        """Selects next flagship model cycling: Qwen -> DeepSeek -> GLM -> Kimi."""
        # Pick the family in the round-robin sequence
        family = FLAGSHIP_FAMILY_ORDER[self._flagship_family_idx % len(FLAGSHIP_FAMILY_ORDER)]
        self._flagship_family_idx = (self._flagship_family_idx + 1) % len(FLAGSHIP_FAMILY_ORDER)

        # Pick the model within that family
        models = get_models_by_tier(family, "flagship")
        if not models:
            # Fallback to Qwen flagship if family models empty
            models = get_models_by_tier("qwen", "flagship")

        m_idx = self._family_model_indices.get(family, 0)
        selected_model = models[m_idx % len(models)]
        self._family_model_indices[family] = (m_idx + 1) % len(models)

        if selected_model in EXHAUSTED_MODELS:
            logger.warning(f"Router encountered exhausted model {selected_model}, skipping.")
            return self._next_cross_family_flagship()

        logger.info(f"[ModelRouter] Selected flagship model '{selected_model}' (Family: {family}) for quality-critical task")
        return selected_model

    def _next_qwen_fast(self) -> str:
        """Selects next fast model cycling within Qwen fast tier."""
        fast_models = get_models_by_tier("qwen", "fast")
        if not fast_models:
            fast_models = ["qwen-turbo", "qwen3.7-flash"]

        selected = fast_models[self._qwen_fast_idx % len(fast_models)]
        self._qwen_fast_idx = (self._qwen_fast_idx + 1) % len(fast_models)

        if selected in EXHAUSTED_MODELS:
            return self._next_qwen_fast()

        logger.info(f"[ModelRouter] Selected fast model '{selected}' (Qwen Fast Tier) for mechanical task")
        return selected

    def _next_qwen_plus(self) -> str:
        """Selects next model cycling within Qwen plus tier."""
        plus_models = get_models_by_tier("qwen", "plus")
        if not plus_models:
            plus_models = ["qwen-plus", "qwen3.7-plus"]

        idx = self._generic_indices.get("qwen_plus", 0)
        selected = plus_models[idx % len(plus_models)]
        self._generic_indices["qwen_plus"] = (idx + 1) % len(plus_models)

        if selected in EXHAUSTED_MODELS:
            return self._next_qwen_plus()

        logger.info(f"[ModelRouter] Selected plus model '{selected}'")
        return selected

    def get_ensemble_models(self, task: str = "moment_extraction", count: int = 3) -> List[str]:
        """
        Returns `count` flagship models, each strictly from a different family.
        e.g., for count=3: [Qwen, DeepSeek, GLM] or [DeepSeek, GLM, Kimi].
        """
        families_to_use = FLAGSHIP_FAMILY_ORDER[:count]
        ensemble_models: List[str] = []

        for fam in families_to_use:
            models = get_models_by_tier(fam, "flagship")
            valid = [m for m in models if m not in EXHAUSTED_MODELS]
            if valid:
                m_idx = self._family_model_indices.get(fam, 0)
                selected = valid[m_idx % len(valid)]
                self._family_model_indices[fam] = (m_idx + 1) % len(valid)
                ensemble_models.append(selected)

        logger.info(f"[ModelRouter] Ensembling configured for {task} with {len(ensemble_models)} cross-family models: {ensemble_models}")
        return ensemble_models

    def call_with_fallback(
        self,
        task: str,
        call_fn: Callable[[str], T],
        max_retries: int = 3
    ) -> T:
        """
        Executes call_fn(model_name) with transparent failover.
        On exception, logs warning, moves to next model in pool, and retries.
        Does not crash the pipeline.
        """
        last_error = None
        for attempt in range(max_retries + 1):
            model = self.next(task)
            try:
                logger.info(f"[ModelRouter] Attempt {attempt+1}/{max_retries+1} on task '{task}' with model '{model}'")
                return call_fn(model)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[ModelRouter] Call failed with model '{model}' on task '{task}': {e}. "
                    f"Advancing to next model in pool..."
                )

        logger.error(f"[ModelRouter] All {max_retries+1} attempts failed for task '{task}'. Last error: {last_error}")
        raise RuntimeError(f"ModelRouter failover exhausted for task '{task}': {last_error}") from last_error


# Global singleton router instance
model_router = ModelRouter()
