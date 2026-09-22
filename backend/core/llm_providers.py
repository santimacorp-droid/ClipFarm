"""
Unified Multi-Model Provider Interface
Supports OpenAI, Gemini, SiliconFlow, Alibaba DashScope, etc.
"""
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

class ProviderType(Enum):
    """Model provider type"""
    DASHSCOPE = "dashscope"      # Alibaba Qwen
    OPENAI = "openai"            # OpenAI
    GEMINI = "gemini"            # Google Gemini
    ANTHROPIC = "anthropic"      # Anthropic Claude
    DEEPSEEK = "deepseek"        # DeepSeek Direct
    OPENROUTER = "openrouter"    # OpenRouter Multi-Model Gateway
    GROQ = "groq"                # Groq Ultra-Fast
    SILICONFLOW = "siliconflow"  # SiliconFlow
    OLLAMA = "ollama"            # Local Ollama
    LMSTUDIO = "lmstudio"        # Local LM Studio
    CUSTOM = "custom"            # Custom OpenAI-compatible API

@dataclass
class ModelInfo:
    """Model information"""
    name: str
    display_name: str
    provider: ProviderType
    max_tokens: int
    cost_per_token: Optional[float] = None
    description: Optional[str] = None

@dataclass
class LLMResponse:
    """LLM Response"""
    content: str
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, api_key: str, model_name: str, **kwargs):
        self.api_key = api_key
        self.model_name = model_name
        self.kwargs = kwargs
    
    @abstractmethod
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """
        Call model API
        
        Args:
            prompt: Prompt text
            input_data: Input data
            **kwargs: Other parameters
            
        Returns:
            LLMResponse: Model response
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test API connection
        
        Returns:
            bool: Whether connection succeeded
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        """
        Get list of available models
        
        Returns:
            List[ModelInfo]: Available model list
        """
        pass
    
    def _build_full_input(self, prompt: str, input_data: Any = None) -> str:
        """Construct complete input"""
        if input_data:
            if isinstance(input_data, dict):
                return f"{prompt}\n\nInput content:\n{json.dumps(input_data, ensure_ascii=False, indent=2)}"
            else:
                return f"{prompt}\n\nInput content:\n{input_data}"
        return prompt

class DashScopeProvider(LLMProvider):
    """Alibaba DashScope Provider"""
    
    def __init__(self, api_key: str, model_name: str = "qwen-plus", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        # Mode: native (SDK Generation.call) | compatible (OpenAI compatible)
        self.mode = (kwargs.get("mode") or os.getenv("DASHSCOPE_MODE") or "native").lower()
        # Compatible mode base_url
        self.base_url = kwargs.get("base_url") or os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        # Native mode SDK
        self._ds_generation = None
        if self.mode == "native":
            try:
                from dashscope import Generation
                self._ds_generation = Generation
            except ImportError:
                raise ImportError("Please install dashscope: pip install dashscope")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """Call DashScope API (mode: native|compatible)"""
        masked_key = self.api_key[:3] + "***" + self.api_key[-2:] if self.api_key else ""
        logger.info(f"[DashScope] mode={self.mode} model={self.model_name} base_url={self.base_url if self.mode=='compatible' else 'sdk-generation'} key={masked_key}")
        logger.info(f"[DashScope] Actual API key in use: {self.api_key}")
        logger.info(f"[DashScope] Provided kwargs: {kwargs}")
        if self.mode == "native":
            try:
                # Ensure provided API key is used by setting env var temporarily
                old_api_key = os.getenv("DASHSCOPE_API_KEY")
                os.environ["DASHSCOPE_API_KEY"] = self.api_key
                
                full_input = self._build_full_input(prompt, input_data)
                resp = self._ds_generation.call(
                    model=self.model_name,
                    prompt=full_input,
                    api_key=self.api_key,
                    stream=False,
                    **kwargs
                )
                
                # Restore original environment variable
                if old_api_key is not None:
                    os.environ["DASHSCOPE_API_KEY"] = old_api_key
                elif "DASHSCOPE_API_KEY" in os.environ:
                    del os.environ["DASHSCOPE_API_KEY"]
                if resp and getattr(resp, 'status_code', 200) == 200:
                    if getattr(resp, 'output', None) and getattr(resp.output, 'text', None) is not None:
                        return LLMResponse(
                            content=resp.output.text,
                            model=self.model_name,
                            finish_reason=getattr(resp.output, 'finish_reason', None)
                        )
                    finish_reason = getattr(resp.output, 'finish_reason', 'unknown') if getattr(resp, 'output', None) else 'unknown'
                    logger.warning(f"API request succeeded, but output is empty. Finish reason: {finish_reason}")
                    return LLMResponse(content="")
                code = getattr(resp, 'code', 'N/A')
                message = getattr(resp, 'message', 'Unknown API error')
                raise Exception(f"API call failed - Status: {getattr(resp,'status_code', 'N/A')}, Code: {code}, Message: {message}")
            except Exception as e:
                logger.error(f"DashScope (native) call failed: {str(e)}")
                raise
        else:
            # compatible
            try:
                import requests
                full_input = self._build_full_input(prompt, input_data)
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": full_input}],
                    "stream": False,
                }
                payload.update({k: v for k, v in kwargs.items() if v is not None})
                url = f"{self.base_url}/chat/completions"
                resp = requests.post(url, headers=headers, json=payload, timeout=90)
                if resp.status_code != 200:
                    try:
                        err = resp.json()
                    except Exception:
                        err = {"message": resp.text}
                    raise Exception(f"API call failed - Status: {resp.status_code}, Message: {err}")
                data = resp.json()
                choice = data["choices"][0]
                msg = choice.get("message", {})
                content = msg.get("content") or ""
                if not content and msg.get("reasoning_content"):
                    content = msg.get("reasoning_content")
                usage = data.get("usage")
                finish_reason = choice.get("finish_reason")
                return LLMResponse(content=content, usage=usage, model=self.model_name, finish_reason=finish_reason)
            except Exception as e:
                logger.error(f"DashScope (compatible) call failed: {str(e)}")
                raise
    
    def test_connection(self) -> bool:
        """Test DashScope connection"""
        try:
            # First validate API Key format
            if not self.api_key or len(self.api_key.strip()) < 10:
                logger.error("API Key is empty or too short")
                return False
            
            # Check API Key format (DashScope API Key typically starts with sk-)
            if not self.api_key.startswith("sk-"):
                logger.warning(f"API Key format may be incorrect, expected to start with 'sk-', actual: {self.api_key[:10]}...")
                # Do not return False directly, as some API Keys may differ in format
            
            # Use simple test call to avoid complex API validation
            try:
                # Call test query directly
                response = self.call("test", max_tokens=1)
                if response and response.content:
                    logger.info("DashScope API connection test successful")
                    return True
                else:
                    logger.error("DashScope API test returned empty response")
                    return False
                    
            except Exception as e:
                logger.error(f"DashScope API test failed: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"DashScope connection test failed: {e}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get available DashScope models"""
        return [
            ModelInfo(
                name="qwen-plus",
                display_name="Qwen Plus",
                provider=ProviderType.DASHSCOPE,
                max_tokens=8192,
                description="Alibaba Qwen Plus model"
            ),
            ModelInfo(
                name="qwen-max",
                display_name="Qwen Max",
                provider=ProviderType.DASHSCOPE,
                max_tokens=8192,
                description="Alibaba Qwen Max model"
            ),
            ModelInfo(
                name="qwen-turbo",
                display_name="Qwen Turbo",
                provider=ProviderType.DASHSCOPE,
                max_tokens=8192,
                description="Alibaba Qwen Turbo model"
            )
        ]

class OpenAIProvider(LLMProvider):
    """OpenAI Provider (and base for OpenAI-compatible endpoints)"""
    
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = base_url or kwargs.get("base_url") or os.getenv("OPENAI_BASE_URL")
        effective_key = api_key if (api_key and str(api_key).strip()) else "local-key"
        try:
            import openai
            client_args = {"api_key": effective_key}
            if self.base_url:
                client_args["base_url"] = str(self.base_url).rstrip("/")
            self.client = openai.OpenAI(**client_args)
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """Call OpenAI API"""
        try:
            full_input = self._build_full_input(prompt, input_data)
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": full_input}],
                **kwargs
            )
            
            content = response.choices[0].message.content or ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason
            )
            
        except Exception as e:
            logger.error(f"OpenAI / Compatible call failed: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """Test OpenAI / Compatible connection"""
        try:
            # Only validate official OpenAI API key format if targeting api.openai.com
            if not self.base_url or "api.openai.com" in str(self.base_url):
                if not self.api_key or len(self.api_key.strip()) < 10:
                    logger.error("OpenAI API Key is empty or too short")
                    return False
                if not self.api_key.startswith("sk-"):
                    logger.warning(f"OpenAI API Key format may be incorrect: {self.api_key[:10]}...")
            
            # Run simple test query
            response = self.call("test", max_tokens=2)
            return response is not None and response.content is not None
        except Exception as e:
            logger.error(f"OpenAI / Compatible connection test failed: {e}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get available OpenAI models"""
        return [
            ModelInfo(
                name="gpt-4o",
                display_name="GPT-4o",
                provider=ProviderType.OPENAI,
                max_tokens=128000,
                description="OpenAI flagship omni model"
            ),
            ModelInfo(
                name="gpt-4o-mini",
                display_name="GPT-4o Mini",
                provider=ProviderType.OPENAI,
                max_tokens=128000,
                description="Fast and affordable OpenAI model"
            ),
            ModelInfo(
                name="gpt-3.5-turbo",
                display_name="GPT-3.5 Turbo",
                provider=ProviderType.OPENAI,
                max_tokens=4096,
                description="OpenAI GPT-3.5 Turbo model"
            ),
            ModelInfo(
                name="gpt-4-turbo",
                display_name="GPT-4 Turbo",
                provider=ProviderType.OPENAI,
                max_tokens=128000,
                description="OpenAI GPT-4 Turbo model"
            )
        ]


class CustomOpenAIProvider(OpenAIProvider):
    """Custom OpenAI-compatible provider (DeepSeek, OpenRouter, vLLM, LM Studio, etc.)"""
    
    def __init__(self, api_key: str, model_name: str = "custom-model", base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, model_name, base_url=base_url, **kwargs)

    def get_available_models(self) -> List[ModelInfo]:
        """Try to fetch remote models from OpenAI-compatible /v1/models endpoint."""
        models: List[ModelInfo] = []
        try:
            remote_models = self.client.models.list()
            for m in getattr(remote_models, "data", []):
                m_id = getattr(m, "id", None) or str(m)
                models.append(
                    ModelInfo(
                        name=m_id,
                        display_name=m_id,
                        provider=ProviderType.CUSTOM,
                        max_tokens=32768,
                        description=f"Custom endpoint model: {m_id}"
                    )
                )
        except Exception as e:
            logger.debug(f"Could not list remote models from custom endpoint: {e}")

        if not models:
            models.append(
                ModelInfo(
                    name=self.model_name or "custom-model",
                    display_name=self.model_name or "Custom Model",
                    provider=ProviderType.CUSTOM,
                    max_tokens=32768,
                    description="Custom OpenAI-compatible model"
                )
            )
        return models


class OllamaProvider(OpenAIProvider):
    """Local Ollama / LM Studio Provider"""
    
    def __init__(self, api_key: str = "", model_name: str = "llama3.2", base_url: Optional[str] = None, **kwargs):
        default_url = base_url or kwargs.get("base_url") or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1"
        super().__init__(api_key or "ollama", model_name or "llama3.2", base_url=default_url, **kwargs)

    def get_available_models(self) -> List[ModelInfo]:
        """Query local Ollama instance for installed models."""
        models: List[ModelInfo] = []
        try:
            remote_models = self.client.models.list()
            for m in getattr(remote_models, "data", []):
                m_id = getattr(m, "id", None) or str(m)
                models.append(
                    ModelInfo(
                        name=m_id,
                        display_name=m_id,
                        provider=ProviderType.OLLAMA,
                        max_tokens=32768,
                        description=f"Local Ollama model: {m_id}"
                    )
                )
        except Exception as e:
            logger.debug(f"Could not query local Ollama models: {e}")

        if not models:
            common_local = [
                ("llama3.2", "Llama 3.2 (3B/1B)"),
                ("llama3.1:8b", "Llama 3.1 8B"),
                ("qwen2.5:7b", "Qwen 2.5 7B"),
                ("mistral:7b", "Mistral 7B"),
                ("deepseek-r1:8b", "DeepSeek R1 (8B Local)")
            ]
            models = [
                ModelInfo(
                    name=name,
                    display_name=display,
                    provider=ProviderType.OLLAMA,
                    max_tokens=32768,
                    description=f"Local Ollama model: {name}"
                )
                for name, display in common_local
            ]
        return models


class LMStudioProvider(OpenAIProvider):
    """Local LM Studio Provider"""

    def __init__(self, api_key: str = "", model_name: str = "local-model", base_url: Optional[str] = None, **kwargs):
        default_url = base_url or kwargs.get("base_url") or os.getenv("LMSTUDIO_BASE_URL") or "http://localhost:1234/v1"
        super().__init__(api_key or "local", model_name or "local-model", base_url=default_url, **kwargs)

    def get_available_models(self) -> List[ModelInfo]:
        """Query local LM Studio instance for currently loaded models."""
        models: List[ModelInfo] = []
        try:
            remote_models = self.client.models.list()
            for m in getattr(remote_models, "data", []):
                m_id = getattr(m, "id", None) or str(m)
                models.append(
                    ModelInfo(
                        name=m_id,
                        display_name=f"LM Studio: {m_id}",
                        provider=ProviderType.LMSTUDIO,
                        max_tokens=32768,
                        description=f"LM Studio local model: {m_id}"
                    )
                )
        except Exception as e:
            logger.debug(f"Could not query LM Studio models: {e}")

        if not models:
            models.append(
                ModelInfo(
                    name=self.model_name or "local-model",
                    display_name=f"LM Studio Loaded Model ({self.model_name})",
                    provider=ProviderType.LMSTUDIO,
                    max_tokens=32768,
                    description="Currently loaded model in LM Studio"
                )
            )
        return models


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek Direct Provider (api.deepseek.com)"""

    def __init__(self, api_key: str, model_name: str = "deepseek-chat", base_url: Optional[str] = None, **kwargs):
        default_url = base_url or "https://api.deepseek.com/v1"
        super().__init__(api_key, model_name or "deepseek-chat", base_url=default_url, **kwargs)

    def get_available_models(self) -> List[ModelInfo]:
        return [
            ModelInfo(
                name="deepseek-chat",
                display_name="DeepSeek V3 (Chat)",
                provider=ProviderType.DEEPSEEK,
                max_tokens=65536,
                description="DeepSeek V3 general intelligence flagship"
            ),
            ModelInfo(
                name="deepseek-reasoner",
                display_name="DeepSeek R1 (Reasoner)",
                provider=ProviderType.DEEPSEEK,
                max_tokens=65536,
                description="DeepSeek R1 reasoning model"
            )
        ]


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter Multi-Model Gateway (Claude, Llama, Mistral, DeepSeek)"""

    def __init__(self, api_key: str, model_name: str = "anthropic/claude-3.5-sonnet", base_url: Optional[str] = None, **kwargs):
        default_url = base_url or "https://openrouter.ai/api/v1"
        super().__init__(api_key, model_name or "anthropic/claude-3.5-sonnet", base_url=default_url, **kwargs)

    def get_available_models(self) -> List[ModelInfo]:
        models: List[ModelInfo] = []
        try:
            remote_models = self.client.models.list()
            for m in getattr(remote_models, "data", []):
                m_id = getattr(m, "id", None) or str(m)
                models.append(
                    ModelInfo(
                        name=m_id,
                        display_name=m_id,
                        provider=ProviderType.OPENROUTER,
                        max_tokens=128000,
                        description=f"OpenRouter: {m_id}"
                    )
                )
        except Exception as e:
            logger.debug(f"Could not query OpenRouter models: {e}")

        if not models:
            popular = [
                ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet (OpenRouter)"),
                ("deepseek/deepseek-r1", "DeepSeek R1 (OpenRouter)"),
                ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B (OpenRouter)"),
                ("mistralai/mistral-large-2411", "Mistral Large 2 (OpenRouter)"),
                ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash (OpenRouter)")
            ]
            models = [
                ModelInfo(
                    name=name,
                    display_name=display,
                    provider=ProviderType.OPENROUTER,
                    max_tokens=128000,
                    description=f"OpenRouter model: {name}"
                )
                for name, display in popular
            ]
        return models


class GroqProvider(OpenAIProvider):
    """Groq Ultra-Fast Inference Provider (api.groq.com)"""

    def __init__(self, api_key: str, model_name: str = "llama-3.3-70b-versatile", base_url: Optional[str] = None, **kwargs):
        default_url = base_url or "https://api.groq.com/openai/v1"
        super().__init__(api_key, model_name or "llama-3.3-70b-versatile", base_url=default_url, **kwargs)

    def get_available_models(self) -> List[ModelInfo]:
        models: List[ModelInfo] = []
        try:
            remote_models = self.client.models.list()
            for m in getattr(remote_models, "data", []):
                m_id = getattr(m, "id", None) or str(m)
                models.append(
                    ModelInfo(
                        name=m_id,
                        display_name=m_id,
                        provider=ProviderType.GROQ,
                        max_tokens=128000,
                        description=f"Groq: {m_id}"
                    )
                )
        except Exception as e:
            logger.debug(f"Could not query Groq models: {e}")

        if not models:
            models = [
                ModelInfo(name="llama-3.3-70b-versatile", display_name="Llama 3.3 70B Versatile", provider=ProviderType.GROQ, max_tokens=128000),
                ModelInfo(name="llama-3.1-8b-instant", display_name="Llama 3.1 8B Instant", provider=ProviderType.GROQ, max_tokens=128000),
                ModelInfo(name="qwen-2.5-32b", display_name="Qwen 2.5 32B (Groq)", provider=ProviderType.GROQ, max_tokens=128000),
                ModelInfo(name="deepseek-r1-distill-llama-70b", display_name="DeepSeek R1 Distill 70B", provider=ProviderType.GROQ, max_tokens=128000),
            ]
        return models


class AnthropicProvider(LLMProvider):
    """Anthropic Claude Provider via Messages API"""

    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022", **kwargs):
        super().__init__(api_key, model_name or "claude-3-5-sonnet-20241022", **kwargs)
        self.base_url = kwargs.get("base_url") or os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1"

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        import requests
        full_input = self._build_full_input(prompt, input_data)
        max_tokens = kwargs.get("max_tokens") or 4096

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": full_input}],
        }
        try:
            response = requests.post(f"{self.base_url.rstrip('/')}/messages", headers=headers, json=data, timeout=120)
            response.raise_for_status()
            res_json = response.json()
            content = ""
            for block in res_json.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            usage = res_json.get("usage")
            return LLMResponse(content=content, usage=usage, model=self.model_name, finish_reason=res_json.get("stop_reason"))
        except Exception as e:
            logger.error(f"Anthropic call failed: {e}")
            raise

    def test_connection(self) -> bool:
        try:
            if not self.api_key or len(self.api_key.strip()) < 10:
                logger.error("Anthropic API key is empty or too short")
                return False
            resp = self.call("hi", max_tokens=5)
            return bool(resp and resp.content)
        except Exception as e:
            logger.error(f"Anthropic connection test failed: {e}")
            return False

    def get_available_models(self) -> List[ModelInfo]:
        return [
            ModelInfo(name="claude-3-5-sonnet-20241022", display_name="Claude 3.5 Sonnet", provider=ProviderType.ANTHROPIC, max_tokens=200000, description="Most capable Anthropic model"),
            ModelInfo(name="claude-3-5-haiku-20241022", display_name="Claude 3.5 Haiku", provider=ProviderType.ANTHROPIC, max_tokens=200000, description="Fastest and most affordable Claude"),
            ModelInfo(name="claude-3-opus-20240229", display_name="Claude 3 Opus", provider=ProviderType.ANTHROPIC, max_tokens=200000, description="High complex analysis Claude"),
        ]


class GeminiProvider(LLMProvider):
    """Google Gemini Provider"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            # New unified Google GenAI SDK (replaces the deprecated
            # google-generativeai package).
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError("Please install google-genai: pip install google-genai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """Call Gemini API"""
        try:
            full_input = self._build_full_input(prompt, input_data)

            # Map a max-tokens hint onto the new SDK's config object if present.
            config = None
            max_tokens = kwargs.get("max_tokens") or kwargs.get("max_output_tokens")
            if max_tokens:
                from google.genai import types
                config = types.GenerateContentConfig(max_output_tokens=max_tokens)

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_input,
                config=config,
            )

            return LLMResponse(
                content=response.text,
                model=self.model_name,
                finish_reason=getattr(response, 'finish_reason', None)
            )

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str:
                logger.warning("Gemini daily quota reached (429), automatically falling back to DashScope (qwen-plus)...")
                import os
                from .llm_providers import DashScopeProvider
                dash_key = os.getenv("API_DASHSCOPE_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
                if dash_key:
                    fallback_provider = DashScopeProvider(
                        api_key=dash_key,
                        model_name="qwen-plus",
                        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
                        mode="compatible"
                    )
                    return fallback_provider.call(prompt, input_data, **kwargs)
            logger.error(f"Gemini call failed: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """Test Gemini connection"""
        try:
            # Use simple test prompt
            response = self.call("test", max_tokens=10)
            # Check if response is valid
            if response and response.content:
                return True
            return False
        except Exception as e:
            logger.error(f"Gemini connection test failed: {e}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get available Gemini models"""
        return [
            ModelInfo(
                name="gemini-2.5-flash",
                display_name="Gemini 2.5 Flash",
                provider=ProviderType.GEMINI,
                max_tokens=1000000,
                description="Google Gemini 2.5 Flash model"
            ),
            ModelInfo(
                name="gemini-1.5-pro",
                display_name="Gemini 1.5 Pro",
                provider=ProviderType.GEMINI,
                max_tokens=2000000,
                description="Google Gemini 1.5 Pro model"
            ),
            ModelInfo(
                name="gemini-1.5-flash",
                display_name="Gemini 1.5 Flash",
                provider=ProviderType.GEMINI,
                max_tokens=1000000,
                description="Google Gemini 1.5 Flash model"
            )
        ]

class SiliconFlowProvider(LLMProvider):
    """SiliconFlow Provider"""
    
    def __init__(self, api_key: str, model_name: str = "Qwen/Qwen2.5-7B-Instruct", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = "https://api.siliconflow.cn/v1"
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """Call SiliconFlow API"""
        try:
            import requests
            
            full_input = self._build_full_input(prompt, input_data)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": full_input}],
                "stream": False,
                **kwargs
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=90
            )
            
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage")
            
            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=result["choices"][0].get("finish_reason")
            )
            
        except Exception as e:
            logger.error(f"SiliconFlow call failed: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """Test SiliconFlow connection"""
        try:
            # Use simple test prompt
            response = self.call("test", max_tokens=10)
            # Check if response is valid
            if response and response.content:
                return True
            return False
        except Exception as e:
            logger.error(f"SiliconFlow connection test failed: {e}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get available SiliconFlow models"""
        return [
            ModelInfo(
                name="Qwen/Qwen2.5-7B-Instruct",
                display_name="Qwen2.5-7B",
                provider=ProviderType.SILICONFLOW,
                max_tokens=32768,
                description="SiliconFlow Qwen2.5-7B model"
            ),
            ModelInfo(
                name="Qwen/Qwen2.5-14B-Instruct",
                display_name="Qwen2.5-14B",
                provider=ProviderType.SILICONFLOW,
                max_tokens=32768,
                description="SiliconFlow Qwen2.5-14B model"
            ),
            ModelInfo(
                name="Qwen/Qwen2.5-32B-Instruct",
                display_name="Qwen2.5-32B",
                provider=ProviderType.SILICONFLOW,
                max_tokens=32768,
                description="SiliconFlow Qwen2.5-32B model"
            ),
            ModelInfo(
                name="deepseek-ai/DeepSeek-V2.5",
                display_name="DeepSeek-V2.5",
                provider=ProviderType.SILICONFLOW,
                max_tokens=65536,
                description="SiliconFlow DeepSeek-V2.5 model"
            )
        ]

class LLMProviderFactory:
    """LLM Provider Factory"""
    
    _providers = {
        ProviderType.DASHSCOPE: DashScopeProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.GEMINI: GeminiProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.DEEPSEEK: DeepSeekProvider,
        ProviderType.OPENROUTER: OpenRouterProvider,
        ProviderType.GROQ: GroqProvider,
        ProviderType.SILICONFLOW: SiliconFlowProvider,
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.LMSTUDIO: LMStudioProvider,
        ProviderType.CUSTOM: CustomOpenAIProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_type: ProviderType, api_key: str, model_name: str, **kwargs) -> LLMProvider:
        """Create provider instance"""
        if provider_type not in cls._providers:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        
        provider_class = cls._providers[provider_type]
        return provider_class(api_key, model_name, **kwargs)
    
    @classmethod
    def get_all_available_models(cls) -> Dict[ProviderType, List[ModelInfo]]:
        """Get available models across all providers"""
        models = {}
        for provider_type, provider_class in cls._providers.items():
            try:
                # Create temporary instance to retrieve model list
                temp_provider = provider_class("dummy_key", "dummy_model")
                models[provider_type] = temp_provider.get_available_models()
            except Exception as e:
                logger.warning(f"Failed to retrieve model list for {provider_type.value}: {e}")
                models[provider_type] = []
        return models
