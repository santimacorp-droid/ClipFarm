"""
Tests for local and expanded LLM providers in ClipFarm.
Covers OllamaProvider, LMStudioProvider, DeepSeekProvider, OpenRouterProvider,
GroqProvider, AnthropicProvider, LLMManager integration, LLMClient routing, and Settings API.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.core.llm_providers import (
    ProviderType,
    LLMProviderFactory,
    OllamaProvider,
    LMStudioProvider,
    CustomOpenAIProvider,
    DeepSeekProvider,
    OpenRouterProvider,
    GroqProvider,
    AnthropicProvider,
    LLMResponse,
)
from backend.core.llm_manager import LLMManager, get_llm_manager
from backend.utils.llm_client import LLMClient
from backend.main import app

client = TestClient(app)


def test_provider_factory_registration_all():
    """Verify all new providers are registered in LLMProviderFactory."""
    ollama_p = LLMProviderFactory.create_provider(
        ProviderType.OLLAMA,
        api_key="",
        model_name="llama3.2",
        base_url="http://localhost:11434/v1",
    )
    assert isinstance(ollama_p, OllamaProvider)
    assert ollama_p.base_url == "http://localhost:11434/v1"

    lmstudio_p = LLMProviderFactory.create_provider(
        ProviderType.LMSTUDIO,
        api_key="",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
    )
    assert isinstance(lmstudio_p, LMStudioProvider)
    assert lmstudio_p.base_url == "http://localhost:1234/v1"

    deepseek_p = LLMProviderFactory.create_provider(
        ProviderType.DEEPSEEK,
        api_key="sk-test-deepseek",
        model_name="deepseek-chat",
    )
    assert isinstance(deepseek_p, DeepSeekProvider)
    assert deepseek_p.base_url == "https://api.deepseek.com/v1"

    openrouter_p = LLMProviderFactory.create_provider(
        ProviderType.OPENROUTER,
        api_key="sk-or-test",
        model_name="anthropic/claude-3.5-sonnet",
    )
    assert isinstance(openrouter_p, OpenRouterProvider)
    assert openrouter_p.base_url == "https://openrouter.ai/api/v1"

    groq_p = LLMProviderFactory.create_provider(
        ProviderType.GROQ,
        api_key="gsk_test",
        model_name="llama-3.3-70b-versatile",
    )
    assert isinstance(groq_p, GroqProvider)
    assert groq_p.base_url == "https://api.groq.com/openai/v1"

    anthropic_p = LLMProviderFactory.create_provider(
        ProviderType.ANTHROPIC,
        api_key="sk-ant-test",
        model_name="claude-3-5-sonnet-20241022",
    )
    assert isinstance(anthropic_p, AnthropicProvider)


@patch("requests.post")
def test_anthropic_provider_test_connection(mock_post):
    """Verify AnthropicProvider makes proper Messages API call and parses response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "Hello, Claude here!"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5}
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    provider = AnthropicProvider(api_key="sk-ant-valid-key-12345", model_name="claude-3-5-haiku-20241022")
    assert provider.test_connection() is True
    assert mock_post.called
    headers = mock_post.call_args[1]["headers"]
    assert headers["x-api-key"] == "sk-ant-valid-key-12345"
    assert headers["anthropic-version"] == "2023-06-01"


@patch("openai.OpenAI")
def test_ollama_provider_get_available_models(mock_openai_cls):
    """Verify get_available_models queries /v1/models and returns ModelInfo items."""
    mock_instance = MagicMock()
    mock_openai_cls.return_value = mock_instance

    m1 = MagicMock()
    m1.id = "llama3.2:latest"
    m2 = MagicMock()
    m2.id = "qwen2.5:7b"
    mock_instance.models.list.return_value = MagicMock(data=[m1, m2])

    provider = OllamaProvider(base_url="http://localhost:11434/v1")
    models = provider.get_available_models()
    model_names = [m.name for m in models]
    assert "llama3.2:latest" in model_names
    assert "qwen2.5:7b" in model_names


def test_llm_manager_custom_and_ollama_setup():
    """Verify LLMManager initializes providers correctly across provider switches."""
    mgr = LLMManager()
    mgr.settings = {
        "llm_provider": "ollama",
        "model_name": "llama3.2",
        "custom_base_url": "http://localhost:11434/v1",
        "ollama_api_key": "",
    }
    mgr._initialize_provider()
    provider = mgr.current_provider
    assert isinstance(provider, OllamaProvider)

    # Switch to deepseek
    mgr.update_settings({
        "llm_provider": "deepseek",
        "model_name": "deepseek-chat",
        "deepseek_api_key": "sk-test",
    })
    provider = mgr.current_provider
    assert isinstance(provider, DeepSeekProvider)
    assert provider.model_name == "deepseek-chat"
    assert provider.base_url == "https://api.deepseek.com/v1"


@patch.object(OllamaProvider, "call")
def test_llm_client_routes_to_local_provider(mock_call):
    """Verify LLMClient.call uses the active local provider directly."""
    mock_call.return_value = LLMResponse(
        content='{"success": true}',
        model="qwen2.5:7b",
    )

    mgr = get_llm_manager()
    old_settings = mgr.settings.copy()
    try:
        mgr.update_settings({
            "llm_provider": "ollama",
            "model_name": "qwen2.5:7b",
            "custom_base_url": "http://localhost:11434/v1",
            "ollama_api_key": "",
        })

        client_inst = LLMClient()
        response = client_inst.call(
            prompt="Analyze this text",
            task="outline",
        )

        assert response == '{"success": true}'
        assert mock_call.called
    finally:
        mgr.update_settings(old_settings)


@patch.object(OllamaProvider, "test_connection", return_value=True)
def test_settings_test_api_ollama(mock_conn):
    """Verify /settings/test-api succeeds for Ollama without requiring an sk- key."""
    response = client.post(
        "/api/v1/settings/test-api",
        json={
            "provider": "ollama",
            "api_key": "",
            "base_url": "http://localhost:11434/v1",
            "model_name": "llama3.2"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@patch.object(DeepSeekProvider, "test_connection", return_value=True)
def test_settings_test_api_deepseek(mock_conn):
    """Verify /settings/test-api succeeds for DeepSeek."""
    response = client.post(
        "/api/v1/settings/test-api",
        json={
            "provider": "deepseek",
            "api_key": "sk-deepseek-test-key",
            "model_name": "deepseek-chat"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@patch.object(AnthropicProvider, "test_connection", return_value=True)
def test_settings_test_api_anthropic(mock_conn):
    """Verify /settings/test-api succeeds for Anthropic."""
    response = client.post(
        "/api/v1/settings/test-api",
        json={
            "provider": "anthropic",
            "api_key": "sk-ant-test-key-12345",
            "model_name": "claude-3-5-sonnet-20241022"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@patch("openai.OpenAI")
def test_settings_fetch_models(mock_openai_cls):
    """Verify /settings/fetch-models returns model list from OpenAI-compatible endpoint."""
    mock_instance = MagicMock()
    mock_openai_cls.return_value = mock_instance

    m1 = MagicMock()
    m1.id = "llama3.2:3b"
    m2 = MagicMock()
    m2.id = "deepseek-r1:8b"
    mock_instance.models.list.return_value = MagicMock(data=[m1, m2])

    response = client.post(
        "/api/v1/settings/fetch-models",
        json={
            "provider": "ollama",
            "api_key": "",
            "base_url": "http://localhost:11434/v1"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "llama3.2:3b" in data["models"]
    assert "deepseek-r1:8b" in data["models"]
