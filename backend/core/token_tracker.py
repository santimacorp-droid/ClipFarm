"""
Token consumption and pricing rates tracker.
Tracks LLM token usage per provider, model, and project with cost estimation.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Standard model pricing rates (USD per 1,000 tokens)
MODEL_RATES = {
    # Alibaba Qwen
    "qwen-plus": {
        "input_rate": 0.0004,
        "output_rate": 0.0012,
        "input_per_million": 0.40,
        "output_per_million": 1.20,
        "currency": "USD",
        "provider": "Alibaba Cloud",
        "description": "Balanced performance and cost for reasoning and outline extraction"
    },
    "qwen-plus-character": {
        "input_rate": 0.0004,
        "output_rate": 0.0012,
        "input_per_million": 0.40,
        "output_per_million": 1.20,
        "currency": "USD",
        "provider": "Alibaba Cloud",
        "description": "Character and roleplay optimized Qwen Plus variant"
    },
    "qwen3.8-max-0902": {
        "input_rate": 0.0028,
        "output_rate": 0.0084,
        "input_per_million": 2.80,
        "output_per_million": 8.40,
        "currency": "USD",
        "provider": "Alibaba Cloud",
        "description": "Latest flagship Qwen 3.8 Max model for deep video reasoning and viral hooks"
    },
    "qwen-flash-character": {
        "input_rate": 0.0001,
        "output_rate": 0.0002,
        "input_per_million": 0.10,
        "output_per_million": 0.20,
        "currency": "USD",
        "provider": "Alibaba Cloud",
        "description": "Ultra-fast Qwen flash character/dialogue model"
    },
    "qwen-turbo": {
        "input_rate": 0.0001,
        "output_rate": 0.0002,
        "input_per_million": 0.10,
        "output_per_million": 0.20,
        "currency": "USD",
        "provider": "Alibaba Cloud",
        "description": "High-throughput, ultra-low cost model"
    },
    "qwen-max": {
        "input_rate": 0.0028,
        "output_rate": 0.0084,
        "input_per_million": 2.80,
        "output_per_million": 8.40,
        "currency": "USD",
        "provider": "Alibaba Cloud",
        "description": "Flagship Qwen model for complex analysis and scoring"
    },
    "qwen-long": {
        "input_rate": 0.00007,
        "output_rate": 0.00028,
        "input_per_million": 0.07,
        "output_per_million": 0.28,
        "currency": "USD",
        "provider": "Alibaba Cloud",
        "description": "Up to 10M context window for massive video transcripts"
    },

    # OpenAI
    "gpt-4o": {
        "input_rate": 0.0025,
        "output_rate": 0.0100,
        "input_per_million": 2.50,
        "output_per_million": 10.00,
        "currency": "USD",
        "provider": "OpenAI",
        "description": "Omni flagship model with high multilingual reasoning"
    },
    "gpt-4o-mini": {
        "input_rate": 0.00015,
        "output_rate": 0.00060,
        "input_per_million": 0.15,
        "output_per_million": 0.60,
        "currency": "USD",
        "provider": "OpenAI",
        "description": "Fast, cost-efficient small model"
    },
    "gpt-4-turbo": {
        "input_rate": 0.0100,
        "output_rate": 0.0300,
        "input_per_million": 10.00,
        "output_per_million": 30.00,
        "currency": "USD",
        "provider": "OpenAI",
        "description": "High capability 128k context model"
    },
    "gpt-3.5-turbo": {
        "input_rate": 0.0005,
        "output_rate": 0.0015,
        "input_per_million": 0.50,
        "output_per_million": 1.50,
        "currency": "USD",
        "provider": "OpenAI",
        "description": "Legacy economical model"
    },

    # Google Gemini
    "gemini-2.5-flash": {
        "input_rate": 0.000075,
        "output_rate": 0.000300,
        "input_per_million": 0.075,
        "output_per_million": 0.30,
        "currency": "USD",
        "provider": "Google",
        "description": "Fastest and smartest multimodal model with 1M context"
    },
    "gemini-1.5-flash": {
        "input_rate": 0.000075,
        "output_rate": 0.000300,
        "input_per_million": 0.075,
        "output_per_million": 0.30,
        "currency": "USD",
        "provider": "Google",
        "description": "Lightweight, sub-second speed with 1M context"
    },
    "gemini-1.5-pro": {
        "input_rate": 0.00125,
        "output_rate": 0.00500,
        "input_per_million": 1.25,
        "output_per_million": 5.00,
        "currency": "USD",
        "provider": "Google",
        "description": "Best for deep analysis across 2M token context"
    },

    # SiliconFlow
    "deepseek-chat": {
        "input_rate": 0.00014,
        "output_rate": 0.00028,
        "input_per_million": 0.14,
        "output_per_million": 0.28,
        "currency": "USD",
        "provider": "SiliconFlow / DeepSeek",
        "description": "State of the art reasoning at ultra low price"
    },
    "deepseek-coder": {
        "input_rate": 0.00014,
        "output_rate": 0.00028,
        "input_per_million": 0.14,
        "output_per_million": 0.28,
        "currency": "USD",
        "provider": "SiliconFlow / DeepSeek",
        "description": "Code and structured text generation"
    }
}

DEFAULT_RATE = {
    "input_rate": 0.0005,
    "output_rate": 0.0015,
    "input_per_million": 0.50,
    "output_per_million": 1.50,
    "currency": "USD",
    "provider": "Generic",
    "description": "Standard fallback model rate"
}


class TokenTracker:
    """Tracks token consumption and costs locally."""

    def __init__(self):
        from .path_utils import get_data_directory
        self.data_file = get_data_directory() / "token_usage.json"
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load token usage file: {e}")
        return {
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost_usd": 0.0,
            "total_requests": 0,
            "by_model": {},
            "by_provider": {},
            "recent_history": []
        }

    def _save(self):
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save token usage: {e}")

    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record token usage for an LLM API call."""
        total_tokens = prompt_tokens + completion_tokens
        rates = MODEL_RATES.get(model, DEFAULT_RATE)
        
        # Calculate cost in USD
        cost = (prompt_tokens / 1000.0) * rates["input_rate"] + (completion_tokens / 1000.0) * rates["output_rate"]

        # Update totals
        self._data["total_tokens"] = self._data.get("total_tokens", 0) + total_tokens
        self._data["total_prompt_tokens"] = self._data.get("total_prompt_tokens", 0) + prompt_tokens
        self._data["total_completion_tokens"] = self._data.get("total_completion_tokens", 0) + completion_tokens
        self._data["total_cost_usd"] = round(self._data.get("total_cost_usd", 0.0) + cost, 6)
        self._data["total_requests"] = self._data.get("total_requests", 0) + 1

        # By model
        by_model = self._data.setdefault("by_model", {})
        model_entry = by_model.setdefault(model, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "requests": 0
        })
        model_entry["prompt_tokens"] += prompt_tokens
        model_entry["completion_tokens"] += completion_tokens
        model_entry["total_tokens"] += total_tokens
        model_entry["cost_usd"] = round(model_entry["cost_usd"] + cost, 6)
        model_entry["requests"] += 1

        # By provider
        by_provider = self._data.setdefault("by_provider", {})
        provider_entry = by_provider.setdefault(provider, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "requests": 0
        })
        provider_entry["prompt_tokens"] += prompt_tokens
        provider_entry["completion_tokens"] += completion_tokens
        provider_entry["total_tokens"] += total_tokens
        provider_entry["cost_usd"] = round(provider_entry["cost_usd"] + cost, 6)
        provider_entry["requests"] += 1

        # Recent history (keep last 50 calls)
        history = self._data.setdefault("recent_history", [])
        history.insert(0, {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6),
            "project_id": project_id
        })
        if len(history) > 50:
            self._data["recent_history"] = history[:50]

        self._save()
        logger.info(f"Recorded token consumption: {total_tokens} tokens (${cost:.5f}) on {model}")

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6)
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return full usage statistics and current rates."""
        return {
            **self._data,
            "model_rates": MODEL_RATES
        }

    def reset_stats(self):
        """Reset all tracked usage."""
        self._data = {
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost_usd": 0.0,
            "total_requests": 0,
            "by_model": {},
            "by_provider": {},
            "recent_history": []
        }
        self._save()


# Global singleton instance
token_tracker = TokenTracker()
