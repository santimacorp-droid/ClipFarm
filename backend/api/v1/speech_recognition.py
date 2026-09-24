"""
Voice recognition configAPI
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from backend.utils.speech_recognizer import (
    SpeechRecognitionMethod, 
    SpeechRecognitionConfig, 
    SpeechRecognizer,
    generate_subtitle_for_video
)
from backend.core.desktop_config import (
    get_desktop_config, 
    save_desktop_config, 
    DesktopConfig,
    SpeechRecognitionSettings,
    WhisperConfig,
    ApiConfig
)
from backend.services.whisper_model_manager import (
    get_model_manager, 
    WhisperModelManager,
    ModelInfo,
    ModelStatus
)
from backend.services.speech_config_validator import get_config_validator

logger = logging.getLogger(__name__)
router = APIRouter()

# Global speech recognition instance
_speech_recognizer: Optional[SpeechRecognizer] = None

def get_speech_recognizer() -> SpeechRecognizer:
    """Get speech recognition instance"""
    global _speech_recognizer
    if _speech_recognizer is None:
        _speech_recognizer = SpeechRecognizer()
    return _speech_recognizer


# ===== Whisper Run time (on-demand installation))=====

@router.get("/whisper/runtime-status")
async def whisper_runtime_status():
    """Whisper Runtime installation status (frontend polling)). """
    from backend.services import whisper_runtime
    return whisper_runtime.get_status()


@router.post("/whisper/install")
async def whisper_install():
    """Starting background install Whisper Runtime(mlx-whisper). """
    from backend.services import whisper_runtime
    if sys_is_not_darwin():
        raise HTTPException(status_code=400, detail="mlx-whisper Supported only Apple Silicon (macOS)")
    return whisper_runtime.start_install()


@router.post("/whisper/uninstall")
async def whisper_uninstall():
    """Uninstalled Whisper Runtime (does not affect previously downloaded model cache, can be deleted separately)). """
    from backend.services import whisper_runtime
    return whisper_runtime.uninstall()


def sys_is_not_darwin() -> bool:
    import sys
    return sys.platform != "darwin"

class SpeechConfigRequest(BaseModel):
    """Speech recognition configuration request"""
    method: str
    model: Optional[str] = "base"
    openaiApiKey: Optional[str] = None
    aliyunApiKey: Optional[str] = None
    enableTimestamps: Optional[bool] = True
    enablePunctuation: Optional[bool] = True
    enableSpeakerDiarization: Optional[bool] = False
    enableFallback: Optional[bool] = True
    fallbackMethod: Optional[str] = "whisper_local"
    timeout: Optional[int] = 1800  # 30Minutes, better suitedWhisperModel processing
    outputFormat: Optional[str] = "srt"

class SpeechConfigResponse(BaseModel):
    """Speech recognition configuration response"""
    method: str
    model: str
    openaiApiKey: Optional[str] = None
    aliyunApiKey: Optional[str] = None
    enableTimestamps: bool
    enablePunctuation: bool
    enableSpeakerDiarization: bool
    enableFallback: bool
    fallbackMethod: str
    timeout: int
    outputFormat: str

class SpeechMethodStatus(BaseModel):
    """Speech recognition method status"""
    method: str
    available: bool
    message: Optional[str] = None

class WhisperModelInfo(BaseModel):
    """WhisperModel information"""
    name: str
    size: str
    sizeBytes: int
    description: str
    accuracy: str
    speed: str
    status: str  # 'available' | 'downloading' | 'downloaded' | 'error'
    downloadProgress: Optional[int] = None

class TestSpeechServiceRequest(BaseModel):
    """Test speech recognition service request"""
    method: str

class TestSpeechServiceResponse(BaseModel):
    """Testing speech recognition service response"""
    success: bool
    message: str

class DownloadModelRequest(BaseModel):
    """Model download request"""
    model: str

@router.get("/speech-recognition/config")
async def get_speech_config(config: DesktopConfig = Depends(get_desktop_config)):
    """Get speech recognition configuration"""
    try:
        speech_config = config.speech_recognition
        
        return {
            "method": speech_config.method,
            "whisper_config": {
                "model_name": speech_config.whisper_config.model_name,
                "language": speech_config.whisper_config.language,
                "custom_models_dir": speech_config.whisper_config.custom_models_dir,
                "enable_timestamps": speech_config.whisper_config.enable_timestamps,
                "enable_punctuation": speech_config.whisper_config.enable_punctuation,
                "enable_speaker_diarization": speech_config.whisper_config.enable_speaker_diarization,
                "timeout": speech_config.whisper_config.timeout
            },
            "openai_config": {
                "api_key": speech_config.openai_config.api_key,
                "endpoint": getattr(speech_config.openai_config, "endpoint", ""),
                "model_name": getattr(speech_config.openai_config, "model_name", "whisper-1"),
                "language": speech_config.openai_config.language,
                "enable_timestamps": speech_config.openai_config.enable_timestamps,
                "enable_punctuation": speech_config.openai_config.enable_punctuation
            },
            "azure_config": {
                "api_key": speech_config.azure_config.api_key,
                "region": speech_config.azure_config.region,
                "language": speech_config.azure_config.language,
                "enable_timestamps": speech_config.azure_config.enable_timestamps,
                "enable_punctuation": speech_config.azure_config.enable_punctuation
            },
            "google_config": {
                "api_key": speech_config.google_config.api_key,
                "language": speech_config.google_config.language,
                "enable_timestamps": speech_config.google_config.enable_timestamps,
                "enable_punctuation": speech_config.google_config.enable_punctuation
            },
            "aliyun_config": {
                "api_key": speech_config.aliyun_config.api_key,
                "language": speech_config.aliyun_config.language,
                "enable_timestamps": speech_config.aliyun_config.enable_timestamps,
                "enable_punctuation": speech_config.aliyun_config.enable_punctuation
            },
            "custom_api_config": {
                "api_key": speech_config.custom_api_config.api_key,
                "endpoint": speech_config.custom_api_config.endpoint,
                "model_name": getattr(speech_config.custom_api_config, "model_name", "whisper-large-v3"),
                "language": speech_config.custom_api_config.language,
                "enable_timestamps": speech_config.custom_api_config.enable_timestamps,
                "enable_punctuation": speech_config.custom_api_config.enable_punctuation
            },
            "enable_fallback": speech_config.enable_fallback,
            "fallback_method": speech_config.fallback_method,
            "output_format": speech_config.output_format
        }
    except Exception as e:
        logger.error(f"Failed to get speech recognition configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to get speech recognition configuration")

class SpeechConfigUpdateRequest(BaseModel):
    """Speech recognition configuration update request"""
    method: str
    whisper_config: Optional[Dict[str, Any]] = None
    openai_config: Optional[Dict[str, Any]] = None
    azure_config: Optional[Dict[str, Any]] = None
    google_config: Optional[Dict[str, Any]] = None
    aliyun_config: Optional[Dict[str, Any]] = None
    custom_api_config: Optional[Dict[str, Any]] = None
    enable_fallback: Optional[bool] = None
    fallback_method: Optional[str] = None
    output_format: Optional[str] = None


@router.put("/speech-recognition/config")
async def update_speech_config(
    request: SpeechConfigUpdateRequest,
    config: DesktopConfig = Depends(get_desktop_config)
):
    """Update speech recognition configuration"""
    try:
        # Verification method
        try:
            method = SpeechRecognitionMethod(request.method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported speech recognition method: {request.method}")
        
        # Verifying fallback method
        if request.fallback_method:
            try:
                fallback_method = SpeechRecognitionMethod(request.fallback_method)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unsupported rollback method: {request.fallback_method}")
        
        # Updating configuration
        speech_config = config.speech_recognition
        speech_config.method = request.method
        
        # UpdateWhisperConfiguration
        if request.whisper_config:
            for key, value in request.whisper_config.items():
                if hasattr(speech_config.whisper_config, key):
                    setattr(speech_config.whisper_config, key, value)
        
        # UpdateAPIConfiguration
        if request.openai_config:
            for key, value in request.openai_config.items():
                if hasattr(speech_config.openai_config, key):
                    setattr(speech_config.openai_config, key, value)
        
        if request.azure_config:
            for key, value in request.azure_config.items():
                if hasattr(speech_config.azure_config, key):
                    setattr(speech_config.azure_config, key, value)
        
        if request.google_config:
            for key, value in request.google_config.items():
                if hasattr(speech_config.google_config, key):
                    setattr(speech_config.google_config, key, value)
        
        if request.aliyun_config:
            for key, value in request.aliyun_config.items():
                if hasattr(speech_config.aliyun_config, key):
                    setattr(speech_config.aliyun_config, key, value)
        
        if request.custom_api_config:
            for key, value in request.custom_api_config.items():
                if hasattr(speech_config.custom_api_config, key):
                    setattr(speech_config.custom_api_config, key, value)
        
        # Updating other configs
        if request.enable_fallback is not None:
            speech_config.enable_fallback = request.enable_fallback
        
        if request.fallback_method:
            speech_config.fallback_method = request.fallback_method
        
        if request.output_format:
            speech_config.output_format = request.output_format
        
        # Saving configuration
        if save_desktop_config(config):
            logger.info(f"Speech recognition configuration updated: {request.method}")
            return {"message": "Speech recognition configuration updated", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to save config")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update speech recognition configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to update speech recognition configuration")

@router.get("/speech-methods-status", response_model=List[SpeechMethodStatus])
async def get_speech_methods_status():
    """Get speech recognition method status"""
    try:
        recognizer = get_speech_recognizer()
        available_methods = recognizer.get_available_methods()
        
        status_list = []
        for method in SpeechRecognitionMethod:
            available = available_methods.get(method, False)
            message = None
            
            if not available:
                if method == SpeechRecognitionMethod.WHISPER_LOCAL:
                    message = "Installation requiredWhisper"
                elif method == SpeechRecognitionMethod.OPENAI_API:
                    message = "Configuration requiredOpenAI API Key"
                elif method == SpeechRecognitionMethod.ALIYUN_SPEECH:
                    message = "Need to configure AliyunAPI Key"
                else:
                    message = "Service unavailable"
            
            status_list.append(SpeechMethodStatus(
                method=method.value,
                available=available,
                message=message
            ))
        
        return status_list
        
    except Exception as e:
        logger.error(f"Failed to get status of speech recognition method: {e}")
        raise HTTPException(status_code=500, detail="Failed to get status of speech recognition method")

@router.get("/whisper-models")
async def get_whisper_models():
    """GettingWhisperModel information"""
    try:
        model_manager = get_model_manager()
        models_info = model_manager.get_all_models_info()
        
        models = []
        for model_info in models_info:
            models.append({
                "name": model_info.name,
                "size": model_info.size,
                "sizeBytes": model_info.size_bytes,
                "description": model_info.description,
                "accuracy": model_info.accuracy,
                "speed": model_info.speed,
                "status": model_info.status.value,
                "downloadProgress": model_info.download_progress,
                "localPath": model_info.local_path,
                "errorMessage": model_info.error_message
            })
        
        return models
        
    except Exception as e:
        logger.error(f"GettingWhisperModel info failed: {e}")
        raise HTTPException(status_code=500, detail="GettingWhisperModel info failed")

@router.post("/test-speech-service", response_model=TestSpeechServiceResponse)
async def test_speech_service(request: TestSpeechServiceRequest):
    """Test speech recognition service"""
    try:
        recognizer = get_speech_recognizer()
        available_methods = recognizer.get_available_methods()
        
        try:
            method = SpeechRecognitionMethod(request.method)
        except ValueError:
            return TestSpeechServiceResponse(
                success=False,
                message=f"Unsupported speech recognition method: {request.method}"
            )
        
        if available_methods.get(method, False):
            return TestSpeechServiceResponse(
                success=True,
                message=f"{method.value} Service available"
            )
        else:
            return TestSpeechServiceResponse(
                success=False,
                message=f"{method.value} Service unavailable, please check configuration"
            )
            
    except Exception as e:
        logger.error(f"Test speech recognition service failed: {e}")
        return TestSpeechServiceResponse(
            success=False,
            message=f"Test failed: {str(e)}"
        )

@router.post("/whisper-models/download")
async def download_whisper_model(request: DownloadModelRequest):
    """DownloadedWhisperModel"""
    try:
        model_manager = get_model_manager()
        
        # Check if model already exists
        model_info = model_manager.get_model_info(request.model)
        if model_info and model_info.status == ModelStatus.DOWNLOADED:
            return {"message": f"Model {request.model} Already exists", "success": True}
        
        # Starting download
        success = await model_manager.download_model(request.model)
        
        if success:
            return {"message": f"Model {request.model} Download complete", "success": True}
        else:
            raise HTTPException(status_code=500, detail=f"Model {request.model} Download failed")
        
    except Exception as e:
        logger.error(f"DownloadedWhisperModel failed: {e}")
        raise HTTPException(status_code=500, detail=f"DownloadedWhisperModel failed: {str(e)}")

@router.delete("/whisper-models/{model_name}")
async def delete_whisper_model(model_name: str):
    """DeletedWhisperModel"""
    try:
        model_manager = get_model_manager()
        
        # Checking if model exists
        model_info = model_manager.get_model_info(model_name)
        if not model_info or model_info.status != ModelStatus.DOWNLOADED:
            raise HTTPException(status_code=404, detail=f"Model {model_name} Does not exist")
        
        # Deleting model
        success = model_manager.delete_model(model_name)
        
        if success:
            return {"message": f"Model {model_name} Deleted successfully", "success": True}
        else:
            raise HTTPException(status_code=500, detail=f"Deleting model {model_name} Failed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DeletedWhisperModel failed: {e}")
        raise HTTPException(status_code=500, detail=f"DeletedWhisperModel failed: {str(e)}")


@router.get("/whisper-models/{model_name}/status")
async def get_model_status(model_name: str):
    """Get model status"""
    try:
        model_manager = get_model_manager()
        model_info = model_manager.get_model_info(model_name)
        
        if not model_info:
            raise HTTPException(status_code=404, detail=f"Model {model_name} Does not exist")
        
        return {
            "name": model_info.name,
            "status": model_info.status.value,
            "downloadProgress": model_info.download_progress,
            "localPath": model_info.local_path,
            "errorMessage": model_info.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model state: {str(e)}")


@router.post("/whisper-models/{model_name}/cancel-download")
async def cancel_model_download(model_name: str):
    """Cancelled model download"""
    try:
        model_manager = get_model_manager()
        success = model_manager.cancel_download(model_name)
        
        if success:
            return {"message": f"Cancelled model download {model_name} Downloading", "success": True}
        else:
            return {"message": f"Model {model_name} No download in progress", "success": False}
        
    except Exception as e:
        logger.error(f"Cancel model download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cancel model download failed: {str(e)}")


@router.post("/speech-recognition/validate")
async def validate_speech_config(
    request: SpeechConfigUpdateRequest,
    config: DesktopConfig = Depends(get_desktop_config)
):
    """Verify speech transcription configuration"""
    try:
        # Create temporary configuration object for verification
        temp_config = config.speech_recognition.copy()
        
        # Updated temporary config
        temp_config.method = request.method
        
        if request.whisper_config:
            for key, value in request.whisper_config.items():
                if hasattr(temp_config.whisper_config, key):
                    setattr(temp_config.whisper_config, key, value)
        
        if request.openai_config:
            for key, value in request.openai_config.items():
                if hasattr(temp_config.openai_config, key):
                    setattr(temp_config.openai_config, key, value)
        
        if request.azure_config:
            for key, value in request.azure_config.items():
                if hasattr(temp_config.azure_config, key):
                    setattr(temp_config.azure_config, key, value)
        
        if request.google_config:
            for key, value in request.google_config.items():
                if hasattr(temp_config.google_config, key):
                    setattr(temp_config.google_config, key, value)
        
        if request.aliyun_config:
            for key, value in request.aliyun_config.items():
                if hasattr(temp_config.aliyun_config, key):
                    setattr(temp_config.aliyun_config, key, value)
        
        if request.custom_api_config:
            for key, value in request.custom_api_config.items():
                if hasattr(temp_config.custom_api_config, key):
                    setattr(temp_config.custom_api_config, key, value)
        
        if request.enable_fallback is not None:
            temp_config.enable_fallback = request.enable_fallback
        
        if request.fallback_method:
            temp_config.fallback_method = request.fallback_method
        
        if request.output_format:
            temp_config.output_format = request.output_format
        
        # Verifying configuration
        validator = get_config_validator()
        validation_result = validator.validate_config(temp_config)
        
        return {
            "valid": validation_result["valid"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
            "recommendations": validation_result["recommendations"]
        }
        
    except Exception as e:
        logger.error(f"Failed to verify speech transcription configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Config validation failed: {str(e)}")


@router.get("/speech-recognition/recommendations")
async def get_speech_recommendations():
    """Getting suggested speech transcription configuration"""
    try:
        recommendations = {
            "scenarios": {
                "New user": {
                    "method": "whisper_local",
                    "model": "base",
                    "description": "Free offline, balancing accuracy and speed"
                },
                "Professional user": {
                    "method": "openai_api",
                    "model": "whisper-1",
                    "description": "Highest accuracy, suitable for important content"
                },
                "Chinese content": {
                    "method": "aliyun_speech",
                    "model": "default",
                    "description": "Better Chinese recognition"
                },
                "Enterprise application": {
                    "method": "azure_speech",
                    "model": "default",
                    "description": "Enterprise service, stable and reliable"
                }
            },
            "model_guide": {
                "tiny": {
                    "size": "39 MB",
                    "speed": "Fastest",
                    "accuracy": "Lower",
                    "recommended_for": "Real-time processing, fast preview"
                },
                "base": {
                    "size": "74 MB",
                    "speed": "Fast",
                    "accuracy": "Moderate",
                    "recommended_for": "Everyday use, balanced choice"
                },
                "small": {
                    "size": "244 MB",
                    "speed": "Moderate",
                    "accuracy": "Better",
                    "recommended_for": "Important content, knowledge-based videos"
                },
                "medium": {
                    "size": "769 MB",
                    "speed": "Slower",
                    "accuracy": "High",
                    "recommended_for": "Professional use, presentation content"
                },
                "large": {
                    "size": "1550 MB",
                    "speed": "Slowest",
                    "accuracy": "Highest",
                    "recommended_for": "Important projects, highest quality requirements"
                }
            },
            "tips": [
                "First use suggests downloading firstbaseTest modelWhisperModel"
            ]
        }
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to get config suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")