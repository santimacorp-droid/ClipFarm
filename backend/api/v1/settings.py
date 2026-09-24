"""
Setting managementAPIEndpoint forDesktopClient provides settings management functionality.
"""

import os
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

from backend.core.desktop_config import get_desktop_config, is_desktop_mode, DesktopConfig, save_desktop_config
from backend.services.config_sync_service import config_sync_service
from pathlib import Path

router = APIRouter(prefix="/settings", tags=["settings"])


class BasicSettings(BaseModel):
    """Base settings"""
    app_name: str = Field(default="ClipFarm Desktop", description="App name")
    app_version: str = Field(default="1.0.0", description="App version")
    debug_mode: bool = Field(default=False, description="Debug mode")
    auto_start: bool = Field(default=True, description="Automatic startup")


class ServiceSettings(BaseModel):
    """Service settings"""
    host: str = Field(default="127.0.0.1", description="Service host")
    port: int = Field(default=8000, description="Service port")
    max_memory_usage: int = Field(default=2048, description="Maximum memory usage(MB)")
    
    @validator('port')
    def validate_port(cls, v):
        if not 1024 <= v <= 65535:
            raise ValueError('Port number must be between1024-65535between')
        return v
    
    @validator('max_memory_usage')
    def validate_memory(cls, v):
        if not 512 <= v <= 8192:
            raise ValueError('Memory usage limit must be between...512-8192MBbetween')
        return v


class ApiKeys(BaseModel):
    """APIKey settings"""
    dashscope: str = Field(default="", description="Tongyi Qianwen API key")
    openai: str = Field(default="", description="OpenAI API key")
    gemini: str = Field(default="", description="Gemini API key")
    anthropic: str = Field(default="", description="Anthropic Claude API key")
    deepseek: str = Field(default="", description="DeepSeek API key")
    openrouter: str = Field(default="", description="OpenRouter API key")
    groq: str = Field(default="", description="Groq API key")
    siliconflow: str = Field(default="", description="SiliconFlow API key")
    custom: str = Field(default="", description="Custom OpenAI-compatible API key")
    ollama: str = Field(default="", description="Local Ollama API key (optional)")
    lmstudio: str = Field(default="", description="Local LM Studio API key (optional)")
    jimeng_access: str = Field(default="", description="DreamAI Access key")
    jimeng_secret: str = Field(default="", description="DreamAI Secret key")


class ApiSettings(BaseModel):
    """API set"""
    api_keys: ApiKeys = Field(default_factory=ApiKeys, description="API key")
    api_model: str = Field(default="qwen-plus", description="Default model")
    api_max_tokens: int = Field(default=4096, description="maximum Token number")
    api_timeout: int = Field(default=30, description="API Timeout (seconds)")
    custom_base_url: str = Field(default="", description="Custom or Local API Base URL")
    llm_provider: str = Field(default="dashscope", description="Active LLM provider")
    
    @validator('api_timeout')
    def validate_timeout(cls, v):
        if not 5 <= v <= 300:
            raise ValueError('API Timeout must be between 5-300 seconds')
        return v


class ProcessingSettings(BaseModel):
    """Processing settings"""
    processing_chunk_size: int = Field(default=5000, description="Processing block size")
    processing_min_score: float = Field(default=0.7, description="Minimum rating threshold")
    processing_max_clips: int = Field(default=5, description="Collection max batch count")
    processing_max_retries: int = Field(default=3, description="Maximum retry count")
    
    @validator('processing_chunk_size')
    def validate_chunk_size(cls, v):
        if not 1000 <= v <= 10000:
            raise ValueError('Block size must be between1000-10000between')
        return v
    
    @validator('processing_min_score')
    def validate_min_score(cls, v):
        if not 0.1 <= v <= 1.0:
            raise ValueError('Minimum score threshold must be between...0.1-1.0between')
        return v


class LogSettings(BaseModel):
    """Log settings"""
    log_level: str = Field(default="INFO", description="Log level")
    log_retention_days: int = Field(default=7, description="Log retention days")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        if v not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            raise ValueError('Log level must be one ofDEBUG, INFO, WARNINGorERROR')
        return v
    
    @validator('log_retention_days')
    def validate_retention_days(cls, v):
        if not 1 <= v <= 30:
            raise ValueError('Log retention days must be between1-30between days')
        return v


class PathSettings(BaseModel):
    """Path settings"""
    data_directory: str = Field(description="Data directory")
    cache_directory: str = Field(description="Cache directory")
    temp_directory: str = Field(description="Temporary directory")


class UpdateDataDirRequest(BaseModel):
    """Update data directory request"""
    new_data_directory: str = Field(description="New data directory path")
    migrate: bool = Field(default=True, description="Whether to migrate old directory data.")


class DesktopSettings(BaseModel):
    """completeDesktopset"""
    basic: BasicSettings = Field(default_factory=BasicSettings)
    service: ServiceSettings = Field(default_factory=ServiceSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    logs: LogSettings = Field(default_factory=LogSettings)
    paths: Optional[PathSettings] = Field(default=None, description="Path settings")


def check_desktop_mode(relaxed: bool = True):
    """Checking if inDesktopMode Web In development mode, loosens restrictions for setting and testing connect interfaces.. 
    """
    return True


@router.get("/desktop-mode")
async def check_desktop_mode_endpoint():
    """Checks whether in desktop mode. Used by front end."""
    return {
        "is_desktop_mode": is_desktop_mode(),
        "environment": {
            "AUTOCLIP_DESKTOP_MODE": os.getenv("AUTOCLIP_DESKTOP_MODE"),
            "AUTOCLIP_MODE": os.getenv("AUTOCLIP_MODE"),
            "TAURI_PLATFORM": os.getenv("TAURI_PLATFORM"),
        }
    }


@router.get("/", response_model=DesktopSettings)
async def get_settings():
    """Getting all settings"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        
        # Tries reading from saved settings file.
        settings_file = config.paths.data_dir / "settings.json"
        print(f"Setting file path: {settings_file}")
        print(f"Settings file exists: {settings_file.exists()}")
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                
                print(f"Settings read from file: {saved_settings.get('basic', {}).get('app_name', 'unknown')}")
                
                # Validates and returns saved settings.
                settings = DesktopSettings(**saved_settings)
                return settings
            except Exception as e:
                # Falls back to default configuration if read fails.
                print(f"Failed to read settings file: {e}")
                pass
        
        # Building path settings
        paths = PathSettings(
            data_directory=str(config.paths.data_dir),
            cache_directory=str(config.paths.cache_dir),
            temp_directory=str(config.paths.temp_dir)
        )
        
        # Building complete settings
        settings = DesktopSettings(
            basic=BasicSettings(
                app_name=config.app_name,
                app_version=config.app_version,
                debug_mode=config.debug_mode,
                auto_start=True  # default value
            ),
            service=ServiceSettings(
                host=config.host,
                port=config.port,
                max_memory_usage=config.max_memory_usage
            ),
            api=ApiSettings(
                api_keys=ApiKeys(
                    dashscope=config.dashscope_api_key,
                    openai=config.openai_api_key,
                    gemini=config.gemini_api_key,
                    siliconflow=config.siliconflow_api_key,
                    jimeng_access="",  # default value
                    jimeng_secret=""   # default value
                ),
                api_model=config.default_model,
                api_max_tokens=config.max_tokens,
                api_timeout=config.timeout
            ),
            processing=ProcessingSettings(
                processing_chunk_size=config.chunk_size,
                processing_min_score=config.min_score_threshold,
                processing_max_clips=config.max_clips_per_collection,
                processing_max_retries=config.max_retries
            ),
            logs=LogSettings(
                log_level=config.log_level,
                log_retention_days=config.log_retention_days
            ),
            paths=paths
        )
        
        return settings
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.post("/paths/data-directory")
async def update_data_directory(
    new_path: str,
    migrate_data: bool = True
):
    """Updating data directory"""
    check_desktop_mode()
    
    try:
        from backend.core.desktop_config import set_data_dir
        
        result = set_data_dir(new_path, migrate_data)
        
        if result["success"]:
            return {
                "message": result["message"],
                "new_path": result["new_path"],
                "migrated_files": result.get("migrated_files", []),
                "failed_files": result.get("failed_files", [])
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Updating data directory failed: {str(e)}")

@router.get("/paths/data-directory")
async def get_data_directory_info():
    """Getting data directory information"""
    check_desktop_mode()
    
    try:
        from backend.core.desktop_config import get_data_dir_info
        
        return get_data_dir_info()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data directory information.: {str(e)}")

@router.delete("/")
async def clear_settings(
    config: DesktopConfig = Depends(get_desktop_config)
):
    """Clearing all settings"""
    check_desktop_mode()
    
    try:
        # Reset configuration to default values
        config.dashscope_api_key = ""
        config.openai_api_key = ""
        config.gemini_api_key = ""
        config.siliconflow_api_key = ""
        config.jimeng_access_key = ""
        config.jimeng_secret_key = ""
        
        # Save config
        save_desktop_config(config)
        
        return {"message": "Settings have been cleared", "success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear settings: {str(e)}")

class TestApiRequest(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    model_name: Optional[str] = None
    base_url: Optional[str] = None

@router.post("/test-api")
async def test_api_connection(request: TestApiRequest):
    """Test API connectivity"""
    check_desktop_mode()
    
    try:
        provider_name = (request.provider or "").lower().strip()
        api_key = (request.api_key or "").strip()
        base_url = (request.base_url or "").strip()

        # For cloud providers without custom base_url, validate key format
        local_or_custom = provider_name in ("ollama", "lmstudio", "custom")
        if not local_or_custom and not base_url:
            if not api_key or len(api_key) < 5:
                return {
                    "success": False,
                    "error": "API key is empty or too short. Please check your input.",
                    "provider": request.provider
                }
            if provider_name in ["dashscope", "openai"] and not api_key.startswith("sk-"):
                return {
                    "success": False,
                    "error": f"{request.provider} API key typically starts with 'sk-'. Please verify.",
                    "provider": request.provider
                }
            if provider_name == "anthropic" and not (api_key.startswith("sk-ant-") or api_key.startswith("sk-")):
                return {
                    "success": False,
                    "error": "Anthropic API key typically starts with 'sk-ant-'. Please verify.",
                    "provider": request.provider
                }
            if provider_name == "groq" and not api_key.startswith("gsk_"):
                return {
                    "success": False,
                    "error": "Groq API key typically starts with 'gsk_'. Please verify.",
                    "provider": request.provider
                }
        
        model_name = request.model_name or os.getenv("API_MODEL_NAME")
        
        if provider_name == "dashscope":
            from backend.core.llm_providers import DashScopeProvider
            is_intl = api_key.startswith("sk-ws-") or (base_url and "intl" in base_url)
            default_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1" if is_intl else (base_url or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
            provider_instance = DashScopeProvider(
                api_key=api_key,
                model_name=model_name or "qwen-plus",
                mode="compatible",
                base_url=default_url
            )
        elif provider_name == "openai":
            from backend.core.llm_providers import OpenAIProvider
            provider_instance = OpenAIProvider(api_key=api_key, model_name=model_name or "gpt-4o-mini", base_url=base_url or None)
        elif provider_name == "gemini":
            from backend.core.llm_providers import GeminiProvider
            provider_instance = GeminiProvider(api_key=api_key, model_name=model_name or "gemini-1.5-flash")
        elif provider_name == "anthropic":
            from backend.core.llm_providers import AnthropicProvider
            provider_instance = AnthropicProvider(api_key=api_key, model_name=model_name or "claude-3-5-sonnet-20241022", base_url=base_url or None)
        elif provider_name == "deepseek":
            from backend.core.llm_providers import DeepSeekProvider
            provider_instance = DeepSeekProvider(api_key=api_key, model_name=model_name or "deepseek-chat", base_url=base_url or "https://api.deepseek.com/v1")
        elif provider_name == "openrouter":
            from backend.core.llm_providers import OpenRouterProvider
            provider_instance = OpenRouterProvider(api_key=api_key, model_name=model_name or "anthropic/claude-3.5-sonnet", base_url=base_url or "https://openrouter.ai/api/v1")
        elif provider_name == "groq":
            from backend.core.llm_providers import GroqProvider
            provider_instance = GroqProvider(api_key=api_key, model_name=model_name or "llama-3.3-70b-versatile", base_url=base_url or "https://api.groq.com/openai/v1")
        elif provider_name == "siliconflow":
            from backend.core.llm_providers import SiliconFlowProvider
            provider_instance = SiliconFlowProvider(api_key=api_key, model_name=model_name or "Qwen/Qwen2.5-7B-Instruct")
        elif provider_name == "ollama":
            from backend.core.llm_providers import OllamaProvider
            provider_instance = OllamaProvider(api_key=api_key or "ollama", model_name=model_name or "llama3.2", base_url=base_url or "http://localhost:11434/v1")
        elif provider_name == "lmstudio":
            from backend.core.llm_providers import LMStudioProvider
            provider_instance = LMStudioProvider(api_key=api_key or "local", model_name=model_name or "local-model", base_url=base_url or "http://localhost:1234/v1")
        elif provider_name == "custom":
            from backend.core.llm_providers import CustomOpenAIProvider
            if not base_url:
                return {
                    "success": False,
                    "error": "Base URL is required for custom OpenAI-compatible endpoints.",
                    "provider": request.provider
                }
            provider_instance = CustomOpenAIProvider(api_key=api_key or "local", model_name=model_name or "custom-model", base_url=base_url)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported API provider: {request.provider}")
        
        # Test connection
        test_result = provider_instance.test_connection()
        
        if test_result:
            try:
                from backend.core.token_tracker import token_tracker
                token_tracker.record(request.provider, model_name or "test", 12, 8)
            except Exception as trk_err:
                logger.warning(f"Could not record test token usage: {trk_err}")
            return {
                "success": True,
                "message": f"Successfully connected to {request.provider}!",
                "provider": request.provider
            }
        else:
            return {
                "success": False,
                "error": f"Failed to connect to {request.provider}. Please verify your Base URL, API key, and model.",
                "provider": request.provider
            }
            
    except Exception as e:
        logger.error(f"API Connection test threw an exception: {str(e)}")
        return {
            "success": False,
            "error": f"API Connection test failed: {str(e)}",
            "provider": request.provider
        }


class FetchModelsRequest(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    base_url: Optional[str] = None


@router.get("/local-status")
async def get_local_ai_status():
    """Detect presence and available models of local AI runtimes (Ollama, LM Studio)."""
    check_desktop_mode()
    import httpx

    results = {
        "ollama": {
            "available": False,
            "base_url": "http://localhost:11434/v1",
            "models": [],
            "message": "Ollama service offline"
        },
        "lmstudio": {
            "available": False,
            "base_url": "http://localhost:1234/v1",
            "models": [],
            "message": "LM Studio local server offline"
        }
    }

    async with httpx.AsyncClient(timeout=1.5) as client:
        # Check Ollama native /api/tags
        try:
            r = await client.get("http://localhost:11434/api/tags")
            if r.status_code == 200:
                data = r.json()
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                results["ollama"] = {
                    "available": True,
                    "base_url": "http://localhost:11434/v1",
                    "models": models,
                    "message": f"Online ({len(models)} model{'s' if len(models) != 1 else ''} installed)"
                }
        except Exception:
            pass

        # Check LM Studio /v1/models
        try:
            r = await client.get("http://localhost:1234/v1/models")
            if r.status_code == 200:
                data = r.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                results["lmstudio"] = {
                    "available": True,
                    "base_url": "http://localhost:1234/v1",
                    "models": models,
                    "message": f"Online ({len(models)} model{'s' if len(models) != 1 else ''} loaded)"
                }
        except Exception:
            pass

    return {
        "success": True,
        "data": results
    }


@router.post("/fetch-models")
async def fetch_models(request: FetchModelsRequest):
    """Fetch remote models list from local or custom OpenAI-compatible endpoint."""
    check_desktop_mode()
    try:
        provider = (request.provider or "").lower().strip()
        base_url = (request.base_url or "").strip()
        api_key = (request.api_key or "").strip()

        # Handle Anthropic directly
        if provider == "anthropic":
            return {
                "success": True,
                "models": [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229"
                ],
                "count": 3,
                "provider": request.provider
            }

        # Resolve known endpoint base URLs
        if provider == "ollama":
            if not base_url:
                base_url = "http://localhost:11434/v1"
            # Attempt direct Ollama /api/tags inspection for faster local discovery
            try:
                import httpx
                host = base_url.replace("/v1", "").rstrip("/")
                with httpx.Client(timeout=1.5) as client:
                    resp = client.get(f"{host}/api/tags")
                    if resp.status_code == 200:
                        tag_data = resp.json()
                        tag_models = [m.get("name") for m in tag_data.get("models", []) if m.get("name")]
                        if tag_models:
                            return {
                                "success": True,
                                "models": tag_models,
                                "count": len(tag_models),
                                "provider": request.provider
                            }
            except Exception:
                pass
        elif provider == "lmstudio" and not base_url:
            base_url = "http://localhost:1234/v1"
        elif provider == "deepseek" and not base_url:
            base_url = "https://api.deepseek.com/v1"
        elif provider == "openrouter" and not base_url:
            base_url = "https://openrouter.ai/api/v1"
        elif provider == "groq" and not base_url:
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "openai" and not base_url:
            base_url = "https://api.openai.com/v1"

        if not base_url:
            raise HTTPException(status_code=400, detail="Base URL is required to fetch models")

        import openai
        client = openai.OpenAI(api_key=api_key or "local", base_url=base_url.rstrip("/"), timeout=5.0)
        response = client.models.list()
        
        model_names = []
        for m in getattr(response, "data", []):
            m_id = getattr(m, "id", None) or str(m)
            if m_id:
                model_names.append(m_id)
        
        return {
            "success": True,
            "models": model_names,
            "count": len(model_names),
            "provider": request.provider
        }
    except Exception as e:
        logger.error(f"Failed to fetch models from {request.provider}: {e}")
        return {
            "success": False,
            "error": str(e),
            "models": [],
            "provider": request.provider
        }

@router.put("/", response_model=Dict[str, Any])
async def update_settings(settings: DesktopSettings):
    """Update settings"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        
        # Updating configuration
        config.debug_mode = settings.basic.debug_mode
        config.host = settings.service.host
        config.port = settings.service.port
        config.max_memory_usage = settings.service.max_memory_usage
        
        # updateAPIset
        config.dashscope_api_key = settings.api.api_keys.dashscope
        config.openai_api_key = settings.api.api_keys.openai
        config.gemini_api_key = settings.api.api_keys.gemini
        config.siliconflow_api_key = settings.api.api_keys.siliconflow
        config.default_model = settings.api.api_model
        config.max_tokens = settings.api.api_max_tokens
        config.timeout = settings.api.api_timeout
        
        # Updating processing settings
        config.chunk_size = settings.processing.processing_chunk_size
        config.min_score_threshold = settings.processing.processing_min_score
        config.max_clips_per_collection = settings.processing.processing_max_clips
        config.max_retries = settings.processing.processing_max_retries
        
        # Updating log settings
        config.log_level = settings.logs.log_level
        
        # Saving settings to file
        settings_file = config.paths.data_dir / "settings.json"
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)
        
        # Important: Save main config file to ensure...API keyCritical configurations persisted...
        from backend.core.desktop_config import save_desktop_config
        if not save_desktop_config(config):
            raise HTTPException(status_code=500, detail="Failed to save main configuration file")

        # Update in-memory LLMManager directly so settings take effect immediately
        try:
            from backend.core.llm_manager import get_llm_manager
            llm_mgr = get_llm_manager()
            new_llm_settings = {
                "llm_provider": settings.api.llm_provider or "dashscope",
                "model_name": settings.api.api_model or "qwen-plus",
                "dashscope_api_key": settings.api.api_keys.dashscope,
                "openai_api_key": settings.api.api_keys.openai,
                "gemini_api_key": settings.api.api_keys.gemini,
                "siliconflow_api_key": settings.api.api_keys.siliconflow,
                "custom_api_key": settings.api.api_keys.custom,
                "ollama_api_key": settings.api.api_keys.ollama,
                "custom_base_url": settings.api.custom_base_url,
                "chunk_size": settings.processing.processing_chunk_size,
                "min_score_threshold": settings.processing.processing_min_score,
                "max_clips_per_collection": settings.processing.processing_max_clips,
            }
            llm_mgr.update_settings(new_llm_settings)
        except Exception as llm_err:
            logger.warning(f"Failed to update in-memory LLMManager: {llm_err}")
        
        return {"message": "Settings updated successfully", "settings_file": str(settings_file)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/reset")
async def reset_settings():
    """Reset settings to default values"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        
        # Deleting setting file
        settings_file = config.paths.data_dir / "settings.json"
        if settings_file.exists():
            settings_file.unlink()
        
        # Reloading default configuration
        config._settings = None
        config._paths = None
        
        return {"message": "Settings reset to default values."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")


@router.post("/paths/data-directory", response_model=Dict[str, Any])
async def update_data_directory(payload: UpdateDataDirRequest):
    """Updates data directory (optional data migration). Called by first-run wizard or settings page.. """
    is_desktop = check_desktop_mode(relaxed=True)
    try:
        config = get_desktop_config()
        result = config.set_data_dir(Path(payload.new_data_directory), migrate_from_old=payload.migrate)

        # Synchronization returns new path configuration.
        paths = {
            "data_directory": str(config.paths.data_dir),
            "cache_directory": str(config.paths.cache_dir),
            "temp_directory": str(config.paths.temp_dir),
            "database_url": config.paths.database_url,
        }

        resp = {"message": "Data directory updated successfully", "result": result, "paths": paths}
        if not is_desktop:
            resp["warning"] = "current non-DesktopDevelopment mode but updated path config."
        return resp
    except Exception as e:
        # Returns more detailed error for permission troubleshooting./path/Usage-related issues
        return {
            "message": "Failed to update data directory but skipped (internal test mode).)",
            "error": str(e),
            "hint": "Confirm that the target directory is writable and not system-limited. Select a user home directory path when necessary.",
        }


@router.post("/export")
async def export_settings():
    """Exporting settings"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        settings = await get_settings()
        
        # Creating export file
        export_file = config.paths.data_dir / "clipfarm-settings-export.json"
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)
        
        return {
            "message": "Successfully exported settings",
            "export_file": str(export_file),
            "download_url": f"/api/v1/settings/download/{export_file.name}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exporting settings failed: {str(e)}")


@router.post("/import")
async def import_settings(file: UploadFile = File(...)):
    """Importing settings"""
    check_desktop_mode()
    
    try:
        # Reading uploaded file
        content = await file.read()
        settings_data = json.loads(content.decode('utf-8'))
        
        # Validating settings format
        settings = DesktopSettings(**settings_data)
        
        # Update settings
        result = await update_settings(settings)
        
        return {
            "message": "Settings imported successfully",
            "imported_settings": settings.dict()
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Settings file format error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import settings: {str(e)}")


# Removing duplicatetest_api_connectionfunction


@router.get("/validation")
async def validate_settings():
    """Validating current settings"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        validation_result = config.validate_config()
        
        return {
            "valid": validation_result["valid"],
            "errors": validation_result.get("errors", []),
            "warnings": validation_result.get("warnings", []),
            "recommendations": []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Settings validation failed: {str(e)}")


@router.get("/backup")
async def backup_settings():
    """Backing up settings"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        backup_dir = config.paths.data_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Create backup
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"settings_backup_{timestamp}.json"
        
        settings = await get_settings()
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(settings.dict(), f, indent=2, ensure_ascii=False)
        
        return {
            "message": "Settings backup successful",
            "backup_file": str(backup_file),
            "backup_time": timestamp
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to back up settings: {str(e)}")


@router.get("/backups")
async def list_backups():
    """Listing all backups"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        backup_dir = config.paths.data_dir / "backups"
        
        if not backup_dir.exists():
            return {"backups": []}
        
        backups = []
        for backup_file in backup_dir.glob("settings_backup_*.json"):
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size": stat.st_size,
                "created_time": stat.st_ctime,
                "modified_time": stat.st_mtime
            })
        
        # Sorted by creation time
        backups.sort(key=lambda x: x["created_time"], reverse=True)
        
        return {"backups": backups}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup list: {str(e)}")


@router.get("/available-models")
async def get_available_models():
    """Get available model list with token rates and limits."""
    check_desktop_mode()
    
    try:
        from backend.core.token_tracker import MODEL_RATES
        
        # Categorized models with rates and token limits
        models = {
            "dashscope": [
                {
                    "name": "qwen3.8-max-0902",
                    "display_name": "Qwen 3.8 Max (Flagship)",
                    "max_tokens": 8192,
                    "description": "Flagship Qwen 3.8 Max reasoning model for viral hook generation and scoring",
                    "input_rate": 0.0028,
                    "output_rate": 0.0084,
                    "rate_display": "$2.80 / 1M in · $8.40 / 1M out"
                },
                {
                    "name": "qwen-flash-character",
                    "display_name": "Qwen Flash (Character)",
                    "max_tokens": 8192,
                    "description": "Ultra-fast flash model with dialogue and personality tuning",
                    "input_rate": 0.0001,
                    "output_rate": 0.0002,
                    "rate_display": "$0.10 / 1M in · $0.20 / 1M out"
                },
                {
                    "name": "qwen-plus-character",
                    "display_name": "Qwen Plus (Character)",
                    "max_tokens": 8192,
                    "description": "Optimized for character/dialogue and highlight scoring",
                    "input_rate": 0.0004,
                    "output_rate": 0.0012,
                    "rate_display": "$0.40 / 1M in · $1.20 / 1M out"
                },
                {
                    "name": "qwen-plus",
                    "display_name": "Qwen Plus",
                    "max_tokens": 8192,
                    "description": "Balanced reasoning and outline extraction",
                    "input_rate": 0.0004,
                    "output_rate": 0.0012,
                    "rate_display": "$0.40 / 1M in · $1.20 / 1M out"
                },
                {
                    "name": "qwen-turbo",
                    "display_name": "Qwen Turbo",
                    "max_tokens": 8192,
                    "description": "Fast and economical model",
                    "input_rate": 0.0001,
                    "output_rate": 0.0002,
                    "rate_display": "$0.10 / 1M in · $0.20 / 1M out"
                },
                {
                    "name": "qwen-max",
                    "display_name": "Qwen Max",
                    "max_tokens": 8192,
                    "description": "Flagship high intelligence model",
                    "input_rate": 0.0028,
                    "output_rate": 0.0084,
                    "rate_display": "$2.80 / 1M in · $8.40 / 1M out"
                },
                {
                    "name": "qwen-long",
                    "display_name": "Qwen Long",
                    "max_tokens": 100000,
                    "description": "Large context window for long videos",
                    "input_rate": 0.00007,
                    "output_rate": 0.00028,
                    "rate_display": "$0.07 / 1M in · $0.28 / 1M out"
                }
            ],
            "openai": [
                {
                    "name": "gpt-4o",
                    "display_name": "GPT-4 Omni",
                    "max_tokens": 128000,
                    "description": "Flagship multimodal intelligence",
                    "input_rate": 0.0025,
                    "output_rate": 0.0100,
                    "rate_display": "$2.50 / 1M in · $10.00 / 1M out"
                },
                {
                    "name": "gpt-4o-mini",
                    "display_name": "GPT-4 Omni Mini",
                    "max_tokens": 128000,
                    "description": "Fast, cost-efficient small model",
                    "input_rate": 0.00015,
                    "output_rate": 0.00060,
                    "rate_display": "$0.15 / 1M in · $0.60 / 1M out"
                },
                {
                    "name": "gpt-4-turbo",
                    "display_name": "GPT-4 Turbo",
                    "max_tokens": 128000,
                    "description": "High performance 128k context",
                    "input_rate": 0.0100,
                    "output_rate": 0.0300,
                    "rate_display": "$10.00 / 1M in · $30.00 / 1M out"
                },
                {
                    "name": "gpt-3.5-turbo",
                    "display_name": "GPT-3.5 Turbo",
                    "max_tokens": 16384,
                    "description": "Economical standard model",
                    "input_rate": 0.0005,
                    "output_rate": 0.0015,
                    "rate_display": "$0.50 / 1M in · $1.50 / 1M out"
                }
            ],
            "gemini": [
                {
                    "name": "gemini-1.5-flash",
                    "display_name": "Gemini 1.5 Flash",
                    "max_tokens": 1000000,
                    "description": "Ultra fast response with 1M context",
                    "input_rate": 0.000075,
                    "output_rate": 0.000300,
                    "rate_display": "$0.075 / 1M in · $0.30 / 1M out"
                },
                {
                    "name": "gemini-1.5-pro",
                    "display_name": "Gemini 1.5 Pro",
                    "max_tokens": 2000000,
                    "description": "State of the art reasoning with 2M context",
                    "input_rate": 0.00125,
                    "output_rate": 0.00500,
                    "rate_display": "$1.25 / 1M in · $5.00 / 1M out"
                }
            ],
            "siliconflow": [
                {
                    "name": "deepseek-chat",
                    "display_name": "DeepSeek Chat (V3)",
                    "max_tokens": 32768,
                    "description": "Advanced reasoning at ultra low price",
                    "input_rate": 0.00014,
                    "output_rate": 0.00028,
                    "rate_display": "$0.14 / 1M in · $0.28 / 1M out"
                },
                {
                    "name": "deepseek-coder",
                    "display_name": "DeepSeek Coder",
                    "max_tokens": 16384,
                    "description": "Code and structured text generation",
                    "input_rate": 0.00014,
                    "output_rate": 0.00028,
                    "rate_display": "$0.14 / 1M in · $0.28 / 1M out"
                }
            ],
        }
        
        return {"models": models}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch model list: {str(e)}")


@router.get("/token-stats")
async def get_token_stats():
    """Get token consumption statistics and model pricing rates."""
    check_desktop_mode()
    try:
        from backend.core.token_tracker import token_tracker
        return token_tracker.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get token stats: {str(e)}")


@router.post("/token-stats/reset")
async def reset_token_stats():
    """Reset token consumption statistics."""
    check_desktop_mode()
    try:
        from backend.core.token_tracker import token_tracker
        token_tracker.reset_stats()
        return {"message": "Token statistics reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset token stats: {str(e)}")


@router.get("/current-provider")
async def get_current_provider():
    """Get current provider and model information."""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        
        provider_info = {
            "provider": getattr(config, "llm_provider", "dashscope"),
            "model": getattr(config, "default_model", None) or os.getenv("API_MODEL_NAME", "qwen-plus-character"),
            "available": True,
            "display_name": "Alibaba Qwen",
            "description": "Alibaba Cloud DashScope Service"
        }
        
        return provider_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get provider info: {str(e)}")


@router.post("/restore/{backup_filename}")
async def restore_backup(backup_filename: str):
    """Restoring settings from backup"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        backup_file = config.paths.data_dir / "backups" / backup_filename
        
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail="Backup file does not exist")
        
        # Reading backup file
        with open(backup_file, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)
        
        # Validate and restore settings
        settings = DesktopSettings(**settings_data)
        result = await update_settings(settings)
        
        return {
            "message": "Settings restored successfully",
            "restored_from": backup_filename,
            "restored_settings": settings.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restore settings: {str(e)}")


@router.post("/sync-config")
async def sync_config():
    """Manual sync of client configuration to backend."""
    check_desktop_mode()
    
    try:
        if config_sync_service.sync_from_client():
            return {
                "status": "success",
                "message": "Successfully synchronized configuration"
            }
        else:
            return {
                "status": "error",
                "message": "Configuration synchronization failed"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Configuration synchronization failed: {str(e)}"
        }


@router.get("/config-status")
async def get_config_status():
    """Configuration synchronization status"""
    check_desktop_mode()
    
    try:
        client_time = config_sync_service.get_client_config_timestamp()
        backup_time = config_sync_service.get_backup_config_timestamp()
        sync_needed = config_sync_service.is_sync_needed()
        
        return {
            "client_config_exists": client_time is not None,
            "backup_config_exists": backup_time is not None,
            "client_config_time": client_time,
            "backup_config_time": backup_time,
            "sync_needed": sync_needed,
            "client_config_path": str(config_sync_service.client_config_path),
            "backup_config_path": str(config_sync_service.backup_config_path)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get configuration status: {str(e)}"
        }