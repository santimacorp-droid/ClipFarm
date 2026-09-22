"""
Duration Configuration Manager
Loads category duration tables from config/clip_duration_config.json with fallback defaults.
Ensures clips can run up to 8 minutes (480s) depending on content category.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Any, Optional

logger = logging.getLogger(__name__)

# Fallback defaults matching requirements
DEFAULT_CATEGORY_DURATION_TABLE: Dict[str, Dict[str, Any]] = {
    # 12 Primary Categories
    "podcast": {"min_sec": 120.0, "max_sec": 360.0, "description": "Long-form podcast conversation segment"},
    "podcast_highlight": {"min_sec": 30.0, "max_sec": 120.0, "description": "Single quotable moment from podcast"},
    "interview": {"min_sec": 60.0, "max_sec": 240.0, "description": "Structured guest Q&A segment"},
    "livestream": {"min_sec": 30.0, "max_sec": 180.0, "description": "Livestream highlights, unscripted rants, and chat interactions"},
    "business_insight": {"min_sec": 45.0, "max_sec": 240.0, "description": "Business, entrepreneurship, finance, career advice"},
    "tech_take": {"min_sec": 45.0, "max_sec": 180.0, "description": "Tech product review, opinion, or news analysis"},
    "ai_moment": {"min_sec": 30.0, "max_sec": 240.0, "description": "AI tools, news, implications, or demonstrations"},
    "gaming_highlight": {"min_sec": 15.0, "max_sec": 90.0, "description": "Gaming moments, reactions, and commentary peaks"},
    "gaming_commentary": {"min_sec": 60.0, "max_sec": 240.0, "description": "Gaming opinions, news, analysis, game reviews"},
    "hot_take": {"min_sec": 30.0, "max_sec": 90.0, "description": "Strong opinion or contrarian take"},
    "funny_moment": {"min_sec": 15.0, "max_sec": 60.0, "description": "Comedic moment — setup and punchline included"},
    "vlog": {"min_sec": 30.0, "max_sec": 180.0, "description": "Personal narrative and day-in-life content"},
    "storytelling": {"min_sec": 60.0, "max_sec": 300.0, "description": "Personal story with complete narrative arc"},
    "default": {"min_sec": 45.0, "max_sec": 180.0, "description": "General fallback"},
    # Legacy fallbacks for backward compatibility
    "entertainment": {"min_sec": 30.0, "max_sec": 90.0, "description": "Entertainment / punchline"},
    "story": {"min_sec": 90.0, "max_sec": 300.0, "description": "Story / narrative arc"},
    "speech": {"min_sec": 120.0, "max_sec": 480.0, "description": "Speech / monologue"},
    "tutorial": {"min_sec": 120.0, "max_sec": 360.0, "description": "Tutorial / explanation"},
    "debate": {"min_sec": 60.0, "max_sec": 240.0, "description": "Debate / reaction"},
    "knowledge": {"min_sec": 120.0, "max_sec": 360.0, "description": "Knowledge & explanation"},
    "business": {"min_sec": 90.0, "max_sec": 300.0, "description": "Business & analysis"},
    "opinion": {"min_sec": 60.0, "max_sec": 240.0, "description": "Opinions & debate"},
    "experience": {"min_sec": 90.0, "max_sec": 300.0, "description": "Experience & how-to"},
    "content_review": {"min_sec": 90.0, "max_sec": 300.0, "description": "Reviews & deep dives"},
}

DEFAULT_GLOBAL_MAX_DURATION = 600.0  # 10 minutes


class DurationConfigManager:
    """Manages clip duration configuration across the pipeline."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            # Look relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "clip_duration_config.json"

        self.config_path = config_path
        self._categories: Dict[str, Dict[str, Any]] = {}
        self._global_max_sec: float = DEFAULT_GLOBAL_MAX_DURATION
        self.reload()

    def reload(self) -> None:
        """Reloads settings from json file, falling back to defaults if missing or corrupted."""
        self._categories = DEFAULT_CATEGORY_DURATION_TABLE.copy()
        self._global_max_sec = DEFAULT_GLOBAL_MAX_DURATION

        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cats = data.get("categories")
                        if isinstance(cats, dict):
                            self._categories.update(cats)
                        if "global_max_duration_sec" in data:
                            self._global_max_sec = float(data["global_max_duration_sec"])
                logger.info(f"Loaded duration configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to parse duration config from {self.config_path}, using defaults: {e}")
        else:
            logger.info(f"Duration config file {self.config_path} not found, using built-in defaults.")

    def get_duration_range(self, category: Optional[str] = None) -> Tuple[float, float]:
        """
        Returns (min_sec, max_sec) for a given category.
        Falls back to 'default' if category is unrecognized.
        """
        cat_key = str(category).lower().strip() if category else "default"
        
        # Mapping aliases
        alias_map = {
            "qa": "interview",
            "q&a": "interview",
            "general": "default",
            "talk": "speech",
            "monologue": "speech",
            "keynote": "speech",
            "review": "content_review"
        }
        cat_key = alias_map.get(cat_key, cat_key)

        cat_info = self._categories.get(cat_key) or self._categories.get("default") or {
            "min_sec": 45.0,
            "max_sec": 180.0
        }
        return float(cat_info.get("min_sec", 45.0)), float(cat_info.get("max_sec", 180.0))

    def get_global_max_sec(self) -> float:
        return self._global_max_sec

    def get_prompt_table_text(self) -> str:
        """Formats the category duration windows into a readable prompt table."""
        lines = [
            "| Category | Expected Duration Range |",
            "| :--- | :--- |",
            "| Entertainment / punchline | 30s – 90s |",
            "| Q&A / interview exchange | 60s – 3 minutes |",
            "| Story / narrative arc | 90s – 5 minutes |",
            "| Speech / monologue | 2 minutes – 8 minutes |",
            "| Tutorial / explanation | 2 minutes – 6 minutes |",
            "| Debate / reaction | 60s – 4 minutes |",
            "| Default (unknown) | 45s – 3 minutes |"
        ]
        return "\n".join(lines)

    def get_prompt_instruction(self, category: Optional[str] = None) -> str:
        """Constructs explicit prompt guidance for duration expectations."""
        min_sec, max_sec = self.get_duration_range(category)
        min_str = f"{int(min_sec)}s" if min_sec < 60 else f"{int(min_sec // 60)}m{int(min_sec % 60)}s" if min_sec % 60 else f"{int(min_sec // 60)}m"
        max_str = f"{int(max_sec)}s" if max_sec < 60 else f"{int(max_sec // 60)}m{int(max_sec % 60)}s" if max_sec % 60 else f"{int(max_sec // 60)}m"
        
        return (
            f"IMPORTANT DURATION GUIDELINE: Clips are NOT restricted to ~1 minute. "
            f"Depending on content type, clips can and should run from 30 seconds up to 8 minutes. "
            f"For category '{category or 'default'}', the target duration window is {min_str} to {max_str}. "
            f"Identify the full, natural narrative arc of each idea or story from opening premise to complete payoff — "
            f"never prematurely truncate or artificially compress a topic to fit short-form format.\n\n"
            f"Reference Duration Table:\n{self.get_prompt_table_text()}"
        )


# Singleton instance
duration_config = DurationConfigManager()
