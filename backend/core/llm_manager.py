"""
LLMManager - Unifies the management of multiple model providers
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from .llm_providers import (
    LLMProvider, LLMProviderFactory, ProviderType, 
    ModelInfo, LLMResponse
)
from ..services.config_sync_service import config_sync_service

logger = logging.getLogger(__name__)

class LLMManager:
    """LLMManager"""
    
    def __init__(self, settings_file: Optional[Path] = None):
        # Synchronize configuration before initialization
        self._sync_config_if_needed()
        
        self.settings_file = settings_file or self._get_default_settings_file()
        self.current_provider: Optional[LLMProvider] = None
        self.settings = self._load_settings()
        self._initialize_provider()
    
    def _get_default_settings_file(self) -> Path:
        """Get default settings file path"""
        from .path_utils import get_default_app_data_dir
        
        # Check standard user app data dir across Windows, macOS, and Linux
        app_dir = get_default_app_data_dir()
        default_settings = app_dir / "settings.json"
        if default_settings.exists():
            return default_settings
            
        # Check the settings.json file in the data directory of project (development environment)
        project_data_dir = Path(__file__).parent.parent.parent / "data"
        project_settings = project_data_dir / "settings.json"
        if project_settings.exists():
            return project_settings
            
        # If none exist, return default path
        return default_settings
    
    def _sync_config_if_needed(self):
        """Check and sync configuration"""
        try:
            if config_sync_service.is_sync_needed():
                logger.info("Detected client configuration update, starting synchronization...")
                if config_sync_service.sync_from_client():
                    logger.info("Configuration synchronized")
                else:
                    logger.warning("Configuration synchronization failed")
        except Exception as e:
            logger.error(f"Configuration synchronization check failed: {e}")
    
    def _load_settings(self) -> Dict[str, Any]:
        """Loading settings"""
        default_settings = {
            "llm_provider": "dashscope",
            "dashscope_api_key": "",
            "openai_api_key": "",
            "gemini_api_key": "",
            "anthropic_api_key": "",
            "deepseek_api_key": "",
            "openrouter_api_key": "",
            "groq_api_key": "",
            "siliconflow_api_key": "",
            "custom_api_key": "",
            "ollama_api_key": "",
            "lmstudio_api_key": "",
            "custom_base_url": "",
            "model_name": "qwen-plus",
            "chunk_size": 5000,
            "min_score_threshold": 0.7,
            "max_clips_per_collection": 5
        }
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    
                    # Handle new configuration format (client configuration)
                    if "api" in saved_settings:
                        api_conf = saved_settings["api"]
                        if "api_keys" in api_conf:
                            api_keys = api_conf["api_keys"]
                            default_settings.update({
                                "dashscope_api_key": api_keys.get("dashscope", ""),
                                "openai_api_key": api_keys.get("openai", ""),
                                "gemini_api_key": api_keys.get("gemini", ""),
                                "anthropic_api_key": api_keys.get("anthropic", ""),
                                "deepseek_api_key": api_keys.get("deepseek", ""),
                                "openrouter_api_key": api_keys.get("openrouter", ""),
                                "groq_api_key": api_keys.get("groq", ""),
                                "siliconflow_api_key": api_keys.get("siliconflow", ""),
                                "custom_api_key": api_keys.get("custom", ""),
                                "ollama_api_key": api_keys.get("ollama", ""),
                                "lmstudio_api_key": api_keys.get("lmstudio", ""),
                            })
                        if "api_model" in api_conf:
                            default_settings["model_name"] = api_conf["api_model"]
                        if "custom_base_url" in api_conf:
                            default_settings["custom_base_url"] = api_conf["custom_base_url"]
                        if "llm_provider" in api_conf:
                            default_settings["llm_provider"] = api_conf["llm_provider"]
                    else:
                        # Handle old configuration format (direct flat)
                        default_settings.update(saved_settings)
                        
            except Exception as e:
                logger.warning(f"Failed to load settings file: {e}")
        
        # Environment variables as fallback
        if not default_settings.get("dashscope_api_key"):
            default_settings["dashscope_api_key"] = os.getenv("API_DASHSCOPE_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or ""
        if not default_settings.get("openai_api_key"):
            default_settings["openai_api_key"] = os.getenv("API_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        if not default_settings.get("gemini_api_key"):
            default_settings["gemini_api_key"] = os.getenv("API_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        if not default_settings.get("anthropic_api_key"):
            default_settings["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY") or ""
        if not default_settings.get("deepseek_api_key"):
            default_settings["deepseek_api_key"] = os.getenv("DEEPSEEK_API_KEY") or ""
        if not default_settings.get("openrouter_api_key"):
            default_settings["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY") or ""
        if not default_settings.get("groq_api_key"):
            default_settings["groq_api_key"] = os.getenv("GROQ_API_KEY") or ""
        if not default_settings.get("siliconflow_api_key"):
            default_settings["siliconflow_api_key"] = os.getenv("API_SILICONFLOW_API_KEY") or os.getenv("SILICONFLOW_API_KEY") or ""
        if not default_settings.get("custom_api_key"):
            default_settings["custom_api_key"] = os.getenv("CUSTOM_API_KEY") or ""
        if not default_settings.get("custom_base_url"):
            default_settings["custom_base_url"] = os.getenv("CUSTOM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
        if os.getenv("LLM_PROVIDER"):
            default_settings["llm_provider"] = os.getenv("LLM_PROVIDER")
        if os.getenv("API_MODEL_NAME"):
            default_settings["model_name"] = os.getenv("API_MODEL_NAME")

        return default_settings
    
    def _save_settings(self):
        """Save settings"""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            raise
    
    def _initialize_provider(self):
        """Initialize current provider"""
        try:
            model_name = self.settings.get("model_name", "qwen-plus")
            configured_provider = self.settings.get("llm_provider", "dashscope")

            # Determine provider type respecting explicit user configuration
            if configured_provider in ("ollama", "lmstudio", "custom", "anthropic", "deepseek", "openrouter", "groq"):
                provider_type = ProviderType(configured_provider)
            elif model_name.startswith("gemini"):
                provider_type = ProviderType.GEMINI
            elif model_name.startswith("gpt-"):
                provider_type = ProviderType.OPENAI
            elif model_name.startswith("claude-"):
                provider_type = ProviderType.ANTHROPIC
            elif model_name.startswith("deepseek-") and configured_provider == "deepseek":
                provider_type = ProviderType.DEEPSEEK
            elif configured_provider == "openai":
                provider_type = ProviderType.OPENAI
            elif configured_provider == "siliconflow":
                provider_type = ProviderType.SILICONFLOW
            elif (
                model_name.startswith("qwen")
                or model_name.startswith("deepseek-")
                or model_name.startswith("kimi-")
                or model_name.startswith("glm-")
                or model_name.startswith("qwq-")
                or model_name.startswith("qvq-")
                or model_name.startswith("fun-")
            ):
                provider_type = ProviderType.DASHSCOPE
            else:
                try:
                    provider_type = ProviderType(configured_provider)
                except ValueError:
                    provider_type = ProviderType.DASHSCOPE
            
            # Get API key for the corresponding provider
            api_key = self._get_api_key_for_provider(provider_type)
            
            if api_key is not None and (api_key or provider_type in (ProviderType.OLLAMA, ProviderType.LMSTUDIO, ProviderType.CUSTOM)):
                extra_kwargs = {}
                custom_url = self.settings.get("custom_base_url") or ""
                
                if provider_type == ProviderType.DASHSCOPE:
                    extra_kwargs["mode"] = os.getenv("DASHSCOPE_MODE", "compatible")
                    extra_kwargs["base_url"] = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
                elif provider_type == ProviderType.OLLAMA:
                    extra_kwargs["base_url"] = custom_url if ("11434" in custom_url or "ollama" in custom_url) else (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1")
                elif provider_type == ProviderType.LMSTUDIO:
                    extra_kwargs["base_url"] = custom_url if ("1234" in custom_url or "lmstudio" in custom_url) else (os.getenv("LMSTUDIO_BASE_URL") or "http://localhost:1234/v1")
                elif provider_type == ProviderType.DEEPSEEK:
                    extra_kwargs["base_url"] = custom_url if "deepseek" in custom_url else "https://api.deepseek.com/v1"
                elif provider_type == ProviderType.OPENROUTER:
                    extra_kwargs["base_url"] = custom_url if "openrouter" in custom_url else "https://openrouter.ai/api/v1"
                elif provider_type == ProviderType.GROQ:
                    extra_kwargs["base_url"] = custom_url if "groq" in custom_url else "https://api.groq.com/openai/v1"
                elif provider_type == ProviderType.CUSTOM and custom_url:
                    extra_kwargs["base_url"] = custom_url
                elif provider_type == ProviderType.OPENAI and custom_url:
                    extra_kwargs["base_url"] = custom_url
                
                self.current_provider = LLMProviderFactory.create_provider(
                    provider_type, api_key, model_name, **extra_kwargs
                )
                logger.info(f"Initialized {provider_type.value} provider, model: {model_name}")
            else:
                logger.warning(f"No API key found for {provider_type.value} provider")
                
        except Exception as e:
            logger.error(f"Provider initialization failed: {e}")
            self.current_provider = None
    
    def _get_api_key_for_provider(self, provider_type: ProviderType) -> Optional[str]:
        """Get API key for the specified provider"""
        key_mapping = {
            ProviderType.DASHSCOPE: "dashscope_api_key",
            ProviderType.OPENAI: "openai_api_key",
            ProviderType.GEMINI: "gemini_api_key",
            ProviderType.ANTHROPIC: "anthropic_api_key",
            ProviderType.DEEPSEEK: "deepseek_api_key",
            ProviderType.OPENROUTER: "openrouter_api_key",
            ProviderType.GROQ: "groq_api_key",
            ProviderType.SILICONFLOW: "siliconflow_api_key",
            ProviderType.CUSTOM: "custom_api_key",
            ProviderType.OLLAMA: "ollama_api_key",
            ProviderType.LMSTUDIO: "lmstudio_api_key",
        }
        
        key_name = key_mapping.get(provider_type)
        if key_name:
            key_val = self.settings.get(key_name, "")
            if not key_val:
                if provider_type in (ProviderType.OLLAMA, ProviderType.LMSTUDIO):
                    return "local"
                if provider_type == ProviderType.CUSTOM and "localhost" in str(self.settings.get("custom_base_url", "")):
                    return "local"
            return key_val
        return None
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """Update settings"""
        self.settings.update(new_settings)
        self._save_settings()
        self._initialize_provider()
    
    def set_provider(self, provider_type: ProviderType, api_key: str, model_name: str):
        """Set provider"""
        try:
            # Update settings
            provider_settings = {
                "llm_provider": provider_type.value,
                "model_name": model_name
            }
            
            # Update API key for the corresponding provider
            key_mapping = {
                ProviderType.DASHSCOPE: "dashscope_api_key",
                ProviderType.OPENAI: "openai_api_key",
                ProviderType.GEMINI: "gemini_api_key",
                ProviderType.ANTHROPIC: "anthropic_api_key",
                ProviderType.DEEPSEEK: "deepseek_api_key",
                ProviderType.OPENROUTER: "openrouter_api_key",
                ProviderType.GROQ: "groq_api_key",
                ProviderType.SILICONFLOW: "siliconflow_api_key",
                ProviderType.CUSTOM: "custom_api_key",
                ProviderType.OLLAMA: "ollama_api_key",
                ProviderType.LMSTUDIO: "lmstudio_api_key",
            }
            
            key_name = key_mapping.get(provider_type)
            if key_name:
                provider_settings[key_name] = api_key
            
            self.update_settings(provider_settings)
            
            # Create new provider instance
            self.current_provider = LLMProviderFactory.create_provider(
                provider_type, api_key, model_name
            )
            
            logger.info(f"Switched to {provider_type.value} provider, model: {model_name}")
            
        except Exception as e:
            logger.error(f"Setting provider failed: {e}")
            raise
    
    def _get_provider_for_model(self, model_name: str):
        """Returns or creates a provider for a specific model name."""
        if not hasattr(self, "_provider_cache"):
            self._provider_cache = {}
        if model_name in self._provider_cache:
            return self._provider_cache[model_name]

        configured_provider = self.settings.get("llm_provider", "dashscope")
        if configured_provider in ("ollama", "lmstudio", "custom", "anthropic", "deepseek", "openrouter", "groq"):
            ptype = ProviderType(configured_provider)
        elif configured_provider == "openai" and not model_name.startswith("gemini"):
            ptype = ProviderType.OPENAI
        elif model_name.startswith("gemini"):
            ptype = ProviderType.GEMINI
        elif model_name.startswith("gpt-"):
            ptype = ProviderType.OPENAI
        elif model_name.startswith("claude-"):
            ptype = ProviderType.ANTHROPIC
        elif configured_provider == "siliconflow":
            ptype = ProviderType.SILICONFLOW
        else:
            ptype = ProviderType.DASHSCOPE

        api_key = self._get_api_key_for_provider(ptype)
        if not api_key and self.current_provider:
            api_key = self.current_provider.api_key

        extra_kwargs = {}
        custom_url = self.settings.get("custom_base_url") or ""

        if ptype == ProviderType.DASHSCOPE:
            extra_kwargs["mode"] = os.getenv("DASHSCOPE_MODE", "compatible")
            extra_kwargs["base_url"] = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
        elif ptype == ProviderType.OLLAMA:
            extra_kwargs["base_url"] = custom_url if ("11434" in custom_url or "ollama" in custom_url) else (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1")
        elif ptype == ProviderType.LMSTUDIO:
            extra_kwargs["base_url"] = custom_url if ("1234" in custom_url or "lmstudio" in custom_url) else (os.getenv("LMSTUDIO_BASE_URL") or "http://localhost:1234/v1")
        elif ptype == ProviderType.DEEPSEEK:
            extra_kwargs["base_url"] = custom_url if "deepseek" in custom_url else "https://api.deepseek.com/v1"
        elif ptype == ProviderType.OPENROUTER:
            extra_kwargs["base_url"] = custom_url if "openrouter" in custom_url else "https://openrouter.ai/api/v1"
        elif ptype == ProviderType.GROQ:
            extra_kwargs["base_url"] = custom_url if "groq" in custom_url else "https://api.groq.com/openai/v1"
        elif ptype == ProviderType.CUSTOM and custom_url:
            extra_kwargs["base_url"] = custom_url
        elif ptype == ProviderType.OPENAI and custom_url:
            extra_kwargs["base_url"] = custom_url

        new_provider = LLMProviderFactory.create_provider(ptype, api_key, model_name, **extra_kwargs)
        self._provider_cache[model_name] = new_provider
        return new_provider

    def call(self, prompt: str, input_data: Any = None, model: Optional[str] = None, **kwargs) -> str:
        """InvocationLLM with optional dynamic model override"""
        provider = self._get_provider_for_model(model) if model else self.current_provider
        if not provider:
            raise ValueError("LLM provider not configured. Please configure API key on the settings page")
        
        try:
            response = provider.call(prompt, input_data, **kwargs)
            try:
                from .token_tracker import token_tracker
                model_name = getattr(response, "model", None) or provider.model_name
                provider_name = self.settings.get("llm_provider", "dashscope")
                project_id = kwargs.get("project_id")
                if response.usage:
                    prompt_tokens = response.usage.get("prompt_tokens") or 0
                    completion_tokens = response.usage.get("completion_tokens") or 0
                else:
                    prompt_len = len(prompt) + (len(str(input_data)) if input_data else 0)
                    completion_len = len(response.content) if response.content else 0
                    prompt_tokens = max(1, prompt_len // 3)
                    completion_tokens = max(1, completion_len // 3)
                token_tracker.record(provider_name, model_name, prompt_tokens, completion_tokens, project_id)
            except Exception as tracker_err:
                logger.warning(f"Failed to record token usage: {tracker_err}")

            return response.content
        except Exception as e:
            logger.error(f"LLMInvocation failed: {e}")
            raise
    
    def call_with_retry(self, prompt: str, input_data: Any = None, max_retries: int = 3, model: Optional[str] = None, **kwargs) -> str:
        """LLM call with retry mechanism and optional model override"""
        for attempt in range(max_retries):
            try:
                return self.call(prompt, input_data, model=model, **kwargs)
            except ValueError:  # Do not retry if API Key or parameter error
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"LLMInvocation in {max_retries} Failed permanently after second retry.")
                    raise
                logger.warning(f"The {attempt + 1} Secondary call failed; preparing to retry: {str(e)}")
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
        return ""
    
    def test_provider_connection(self, provider_type: ProviderType, api_key: str, model_name: str) -> bool:
        """Test provider connection"""
        try:
            provider = LLMProviderFactory.create_provider(provider_type, api_key, model_name)
            return provider.test_connection()
        except Exception as e:
            logger.error(f"Test{provider_type.value}Connection failed: {e}")
            return False
    
    def get_current_provider_info(self) -> Dict[str, Any]:
        """Get current provider information"""
        if not self.current_provider:
            return {"provider": None, "model": None, "available": False}
        
        provider_type = ProviderType(self.settings.get("llm_provider", "dashscope"))
        model_name = self.settings.get("model_name", "qwen-plus")
        
        return {
            "provider": provider_type.value,
            "model": model_name,
            "available": True,
            "display_name": self._get_provider_display_name(provider_type)
        }
    
    def _get_provider_display_name(self, provider_type: ProviderType) -> str:
        """Get provider display name"""
        display_names = {
            ProviderType.DASHSCOPE: "Alibaba Qwen",
            ProviderType.OPENAI: "OpenAI",
            ProviderType.GEMINI: "Google Gemini",
            ProviderType.ANTHROPIC: "Anthropic Claude",
            ProviderType.DEEPSEEK: "DeepSeek",
            ProviderType.OPENROUTER: "OpenRouter Gateway",
            ProviderType.GROQ: "Groq (Ultra-Fast)",
            ProviderType.SILICONFLOW: "SiliconFlow",
            ProviderType.OLLAMA: "Ollama (Local)",
            ProviderType.LMSTUDIO: "LM Studio (Local)",
            ProviderType.CUSTOM: "Custom (OpenAI-Compatible)"
        }
        return display_names.get(provider_type, provider_type.value)
    
    def get_all_available_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available models"""
        all_models = LLMProviderFactory.get_all_available_models()
        result = {}
        
        for provider_type, models in all_models.items():
            provider_name = provider_type.value
            result[provider_name] = [
                {
                    "name": model.name,
                    "display_name": model.display_name,
                    "max_tokens": model.max_tokens,
                    "description": model.description
                }
                for model in models
            ]
        
        return result
    
    def parse_json_response(self, response: str) -> Any:
        """Parse JSON response (maintain compatibility with the original LLMClient))"""
        if not self.current_provider:
            raise ValueError("No LLM provider configured")
        
        # Here we can reuse the original LLMClient's JSON parsing logic
        # To maintain compatibility, we create a temporary LLMClient instance
        from ..utils.llm_client import LLMClient
        temp_client = LLMClient()
        return temp_client.parse_json_response(response)

# Global LLM manager instance
_llm_manager: Optional[LLMManager] = None

def get_llm_manager() -> LLMManager:
    """Get global LLM manager instance"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager

def initialize_llm_manager(settings_file: Optional[Path] = None) -> LLMManager:
    """Initialize LLM manager"""
    global _llm_manager
    _llm_manager = LLMManager(settings_file)
    return _llm_manager
