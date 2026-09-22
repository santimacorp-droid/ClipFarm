"""
Speech-to-Text configuration validation service
Responsible for validating the validity and integrity of the configuration
"""
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from backend.core.desktop_config import SpeechRecognitionSettings, WhisperConfig, ApiConfig
from backend.services.whisper_model_manager import get_model_manager, ModelStatus

logger = logging.getLogger(__name__)


class SpeechConfigValidator:
    """Speech-to-Text configuration validator"""
    
    def __init__(self):
        self.model_manager = get_model_manager()
    
    def validate_config(self, config: SpeechRecognitionSettings) -> Dict[str, any]:
        """
        Validate speech-to-text configuration
        
        Args:
            config: Speech-to-Text configuration
            
        Returns:
            Validate result dictionary
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Validate main method
        method_validation = self._validate_method(config.method)
        if not method_validation["valid"]:
            result["valid"] = False
            result["errors"].extend(method_validation["errors"])
        
        # Validate specific configuration
        if config.method == "whisper_local":
            whisper_validation = self._validate_whisper_config(config.whisper_config)
            if not whisper_validation["valid"]:
                result["valid"] = False
                result["errors"].extend(whisper_validation["errors"])
            result["warnings"].extend(whisper_validation["warnings"])
            result["recommendations"].extend(whisper_validation["recommendations"])
        
        elif config.method in ["openai_api", "azure_speech", "google_speech", "aliyun_speech", "custom_api"]:
            api_validation = self._validate_api_config(config, config.method)
            if not api_validation["valid"]:
                result["valid"] = False
                result["errors"].extend(api_validation["errors"])
            result["warnings"].extend(api_validation["warnings"])
            result["recommendations"].extend(api_validation["recommendations"])
        
        # Validate fallback config
        if config.enable_fallback:
            fallback_validation = self._validate_fallback_config(config)
            if not fallback_validation["valid"]:
                result["warnings"].extend(fallback_validation["warnings"])
        
        return result
    
    def _validate_method(self, method: str) -> Dict[str, any]:
        """Validate method selection"""
        valid_methods = [
            "whisper_local", "openai_api", "azure_speech", 
            "google_speech", "aliyun_speech", "custom_api"
        ]
        
        if method not in valid_methods:
            return {
                "valid": False,
                "errors": [f"Unsupported speech recognition method: {method}"]
            }
        
        return {"valid": True, "errors": []}
    
    def _validate_whisper_config(self, config: WhisperConfig) -> Dict[str, any]:
        """Validate Whisper configuration"""
        result = {"valid": True, "errors": [], "warnings": [], "recommendations": []}
        
        # Validate model name
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if config.model_name not in valid_models:
            result["valid"] = False
            result["errors"].append(f"Not supportedWhisperModel: {config.model_name}")
        
        # Check if model is already downloaded
        model_info = self.model_manager.get_model_info(config.model_name)
        if model_info and model_info.status != ModelStatus.DOWNLOADED:
            if model_info.status == ModelStatus.AVAILABLE:
                result["warnings"].append(f"Model {config.model_name} Not downloaded, will be automatically downloaded when used for the first time")
            elif model_info.status == ModelStatus.DOWNLOADING:
                result["warnings"].append(f"Model {config.model_name} Downloading in progress")
            elif model_info.status == ModelStatus.ERROR:
                result["errors"].append(f"Model {config.model_name} Download failed")
        
        # Validate timeout
        if config.timeout < 60:
            result["warnings"].append("The timeout is too short; it is recommended to set at least 60 seconds")
        elif config.timeout > 7200:
            result["warnings"].append("The timeout is too long; it is recommended not to exceed 2 hours")
        
        # Validate custom model directory
        if config.custom_models_dir:
            custom_dir = Path(config.custom_models_dir)
            if not custom_dir.exists():
                result["errors"].append(f"Custom model directory does not exist: {config.custom_models_dir}")
            elif not custom_dir.is_dir():
                result["errors"].append(f"Custom model directory is not a valid directory: {config.custom_models_dir}")
        
        # Add recommendation
        if config.model_name == "tiny":
            result["recommendations"].append("The tiny model is fastest but has lower accuracy; it is recommended for real-time processing")
        elif config.model_name == "base":
            result["recommendations"].append("The base model is a balanced choice recommended for everyday use")
        elif config.model_name in ["small", "medium", "large"]:
            result["recommendations"].append(f"{config.model_name}Model has high accuracy but slower speed, suitable for important content")
        
        return result
    
    def _validate_api_config(self, config: SpeechRecognitionSettings, method: str) -> Dict[str, any]:
        """Validate API configuration"""
        result = {"valid": True, "errors": [], "warnings": [], "recommendations": []}
        
        # Get corresponding API configuration
        if method == "openai_api":
            api_config = config.openai_config
        elif method == "azure_speech":
            api_config = config.azure_config
        elif method == "google_speech":
            api_config = config.google_config
        elif method == "aliyun_speech":
            api_config = config.aliyun_config
        elif method == "custom_api":
            api_config = config.custom_api_config
        else:
            return {"valid": False, "errors": [f"Not supportedAPIMethod: {method}"]}
        
        # Validate API key
        if not api_config.api_key:
            result["valid"] = False
            result["errors"].append(f"{method} APIAPI key cannot be empty")
        elif len(api_config.api_key) < 10:
            result["warnings"].append("The API key length is too short; please check if it is correct")
        
        # Validate Azure region
        if method == "azure_speech" and not api_config.region:
            result["valid"] = False
            result["errors"].append("The Azure Speech service requires specifying the region")
        
        # Validate custom API endpoint
        if method == "custom_api":
            if not api_config.endpoint:
                result["valid"] = False
                result["errors"].append("Custom API requires specifying the endpoint URL")
            elif not api_config.endpoint.startswith(("http://", "https://")):
                result["errors"].append("The API endpoint must be a valid HTTP/HTTPS URL")
        
        # Add recommendation
        if method == "openai_api":
            result["recommendations"].append("OpenAI API has the highest accuracy but requires payment")
        elif method == "azure_speech":
            result["recommendations"].append("Azure Speech is suitable for enterprise applications and supports multiple languages")
        elif method == "google_speech":
            result["recommendations"].append("Google Speech offers rich functionality and supports real-time recognition")
        elif method == "aliyun_speech":
            result["recommendations"].append("Aliyun Speech Recognition is optimized for Chinese")
        
        return result
    
    def _validate_fallback_config(self, config: SpeechRecognitionSettings) -> Dict[str, any]:
        """Validate fallback config"""
        result = {"valid": True, "warnings": [], "recommendations": []}
        
        # Check whether the fallback method matches the primary method
        if config.fallback_method == config.method:
            result["warnings"].append("Fallback method should match primary method; different fallback methods are suggested")
        
        # Check if fallback method is available
        if config.fallback_method == "whisper_local":
            model_info = self.model_manager.get_model_info(config.whisper_config.model_name)
            if model_info and model_info.status not in [ModelStatus.DOWNLOADED, ModelStatus.AVAILABLE]:
                result["warnings"].append("The fallback method using the Whisper model is unavailable")
        
        # Add recommendation
        if config.method != "whisper_local" and config.fallback_method != "whisper_local":
            result["recommendations"].append("It is recommended to use local Whisper models as fallback for offline availability")
        
        return result
    
    def get_config_recommendations(self, config: SpeechRecognitionSettings) -> List[str]:
        """Get config suggestions"""
        recommendations = []
        
        # Recommended based on usage scenario
        if config.method == "whisper_local":
            if config.whisper_config.model_name == "tiny":
                recommendations.append("The tiny model is suitable for fast processing but has lower accuracy")
            elif config.whisper_config.model_name in ["medium", "large"]:
                recommendations.append("Large models have high accuracy but longer processing times; they are suitable for important content")
        
        # Network environment recommendation
        if config.method != "whisper_local":
            recommendations.append("Using the API service requires a stable network connection")
            if config.enable_fallback and config.fallback_method == "whisper_local":
                recommendations.append("Configured local fallback to ensure offline availability")
        
        # Performance suggestion
        if config.whisper_config.enable_speaker_diarization:
            recommendations.append("The speaker separation feature increases processing time")
        
        return recommendations


# Global validator instance
_validator: Optional[SpeechConfigValidator] = None


def get_config_validator() -> SpeechConfigValidator:
    """Get configuration validator instance"""
    global _validator
    if _validator is None:
        _validator = SpeechConfigValidator()
    return _validator
