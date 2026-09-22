"""
Unified Configuration Management System
Integrates all configuration sources and provides a unified interface for configuration access
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import path_utils

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="sqlite:///./data/autoclip.db", description="Database connectionURL")
    echo: bool = Field(default=False, description="Whether to print SQL statements")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Maximum overflow connection count")


class RedisConfig(BaseModel):
    """Redis configuration"""
    url: str = Field(default="redis://localhost:6379/0", description="RedisConnectionURL")
    max_connections: int = Field(default=10, description="Maximum connection count")
    socket_timeout: int = Field(default=5, description="SocketTimeout")


class APIConfig(BaseModel):
    """API configuration"""
    dashscope_api_key: str = Field(default="", description="DashScope APIKey")
    model_name: str = Field(default="qwen-plus", description="Model name")
    max_tokens: int = Field(default=4096, description="Maximum token count")
    timeout: int = Field(default=30, description="APITimeout")
    max_retries: int = Field(default=3, description="Maximum retry count")
    
    @validator('max_tokens')
    def validate_max_tokens(cls, v):
        if v <= 0:
            raise ValueError('max_tokensMust be greater than0')
        return v
    
    @validator('timeout')
    def validate_timeout(cls, v):
        if v <= 0:
            raise ValueError('timeoutMust be greater than0')
        return v


class ProcessingConfig(BaseModel):
    """Processing configuration"""
    chunk_size: int = Field(default=5000, description="Text block size")
    min_score_threshold: float = Field(default=0.7, description="Minimum score threshold")
    max_clips_per_collection: int = Field(default=5, description="Maximum number of slices per collection")
    max_retries: int = Field(default=3, description="Maximum retry count")
    timeout_seconds: int = Field(default=30, description="Processing timeout")
    
    # Topic extraction control parameters
    min_topic_duration_minutes: int = Field(default=2, description="Minimum topic duration (minutes))")
    max_topic_duration_minutes: int = Field(default=12, description="Maximum topic duration (minutes))")
    target_topic_duration_minutes: int = Field(default=5, description="Target topic duration (minutes))")
    min_topics_per_chunk: int = Field(default=3, description="Minimum number of topics per chunk")
    max_topics_per_chunk: int = Field(default=8, description="Maximum number of topics per chunk")
    
    @validator('min_score_threshold')
    def validate_score_threshold(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('Score threshold must be between 0 and 1')
        return v
    
    @validator('chunk_size')
    def validate_chunk_size(cls, v):
        if v <= 0:
            raise ValueError('Chunk size must be greater than0')
        return v


class SpeechRecognitionConfig(BaseModel):
    """Speech recognition configuration"""
    method: str = Field(default="whisper_local", description="Recognition method")
    language: str = Field(default="auto", description="Recognition language")
    model: str = Field(default="base", description="Model size")
    timeout: int = Field(default=1000, description="Recognition timeout")


class BilibiliConfig(BaseModel):
    """BSite configuration"""
    auto_upload: bool = Field(default=False, description="Auto-upload enabled")
    default_tid: int = Field(default=21, description="Default partitionID")
    max_concurrent_uploads: int = Field(default=3, description="Maximum number of concurrent uploads")
    upload_timeout_minutes: int = Field(default=30, description="Upload timeout (minutes))")
    auto_generate_tags: bool = Field(default=True, description="Whether to auto-generate tags")
    tag_limit: int = Field(default=12, description="Maximum number of tags")


class LoggingConfig(BaseModel):
    """Log configuration"""
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")
    file: str = Field(default="backend.log", description="Log file")
    max_size: int = Field(default=10 * 1024 * 1024, description="Maximum log file size (bytes))")
    backup_count: int = Field(default=5, description="Number of log file backups")


class PathConfig(BaseModel):
    """Path configuration"""
    project_root: Path = Field(default_factory=path_utils.get_project_root)
    data_dir: Path = Field(default_factory=path_utils.get_data_directory)
    uploads_dir: Path = Field(default_factory=path_utils.get_uploads_directory)
    output_dir: Path = Field(default_factory=path_utils.get_output_directory)
    temp_dir: Path = Field(default_factory=path_utils.get_temp_directory)
    prompt_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "prompt")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure all directories exist
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, Path):
                field_value.mkdir(parents=True, exist_ok=True)


class UnifiedConfig(BaseSettings):
    """Unified configuration class"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        env_nested_delimiter='__'
    )
    
    # Environment configuration
    environment: str = Field(default="development", description="Run-time environment")
    debug: bool = Field(default=True, description="Debug mode")
    encryption_key: str = Field(default="", description="Encryption key")
    
    # Sub-configuration
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    speech_recognition: SpeechRecognitionConfig = Field(default_factory=SpeechRecognitionConfig)
    bilibili: BilibiliConfig = Field(default_factory=BilibiliConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_from_files()
        self._setup_environment()
    
    def _load_from_files(self):
        """Loads settings from configuration file"""
        # Load from data/settings.json
        settings_file = self.paths.data_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    file_settings = json.load(f)
                    self._merge_settings(file_settings)
            except Exception as e:
                logger.warning(f"Failed to load configuration file: {e}")
        
        # Load from environment variables
        self._load_from_env()
    
    def _merge_settings(self, settings: Dict[str, Any]):
        """Merges settings into configuration object"""
        for key, value in settings.items():
            if hasattr(self, key):
                if isinstance(getattr(self, key), BaseModel):
                    # If sub‑configuration object, recursively merges
                    sub_config = getattr(self, key)
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if hasattr(sub_config, sub_key):
                                setattr(sub_config, sub_key, sub_value)
                else:
                    setattr(self, key, value)
    
    def _load_from_env(self):
        """Loads configuration from environment variables"""
        # Database configuration
        if os.getenv("DATABASE_URL"):
            self.database.url = os.getenv("DATABASE_URL")
        
        # Redis configuration
        if os.getenv("REDIS_URL"):
            self.redis.url = os.getenv("REDIS_URL")
        
        # API configuration
        if os.getenv("DASHSCOPE_API_KEY"):
            self.api.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        if os.getenv("API_MODEL_NAME"):
            self.api.model_name = os.getenv("API_MODEL_NAME")
        
        # Processing configuration
        if os.getenv("PROCESSING_CHUNK_SIZE"):
            self.processing.chunk_size = int(os.getenv("PROCESSING_CHUNK_SIZE"))
        if os.getenv("PROCESSING_MIN_SCORE_THRESHOLD"):
            self.processing.min_score_threshold = float(os.getenv("PROCESSING_MIN_SCORE_THRESHOLD"))
        
        # Log configuration
        if os.getenv("LOG_LEVEL"):
            self.logging.level = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_FILE"):
            self.logging.file = os.getenv("LOG_FILE")
    
    def _setup_environment(self):
        """Set environment variable"""
        # Sets API key to environment variable
        if self.api.dashscope_api_key:
            os.environ["DASHSCOPE_API_KEY"] = self.api.dashscope_api_key
        
        # Set database URL
        os.environ["DATABASE_URL"] = self.database.url
        
        # Sets Redis URL
        os.environ["REDIS_URL"] = self.redis.url
    
    def save_to_file(self, file_path: Optional[Path] = None):
        """Save configuration to file"""
        if file_path is None:
            file_path = self.paths.data_dir / "settings.json"
        
        try:
            # Creates configuration dictionary, excluding sensitive information
            config_dict = self._to_safe_dict()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Config saved to: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration file: {e}")
            raise
    
    def _to_safe_dict(self) -> Dict[str, Any]:
        """Converts to safe dictionary format (hides sensitive information))"""
        config_dict = {}
        
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            
            if isinstance(value, BaseModel):
                config_dict[key] = value.dict()
            else:
                config_dict[key] = value
        
        # Hide sensitive information
        if 'api' in config_dict and 'dashscope_api_key' in config_dict['api']:
            api_key = config_dict['api']['dashscope_api_key']
            if api_key:
                config_dict['api']['dashscope_api_key'] = api_key[:8] + "..." if len(api_key) > 8 else "***"
        
        return config_dict
    
    def update_config(self, **kwargs):
        """Update configuration"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                if isinstance(getattr(self, key), BaseModel):
                    # If sub‑configuration object, recursively updates
                    sub_config = getattr(self, key)
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if hasattr(sub_config, sub_key):
                                setattr(sub_config, sub_key, sub_value)
                else:
                    setattr(self, key, value)
        
        # Re-set environment variable
        self._setup_environment()
        
        # Save to file
        self.save_to_file()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary"""
        return {
            "environment": self.environment,
            "debug": self.debug,
            "database": {
                "url": self.database.url,
                "echo": self.database.echo
            },
            "redis": {
                "url": self.redis.url
            },
            "api": {
                "model_name": self.api.model_name,
                "max_tokens": self.api.max_tokens,
                "timeout": self.api.timeout,
                "has_api_key": bool(self.api.dashscope_api_key)
            },
            "processing": {
                "chunk_size": self.processing.chunk_size,
                "min_score_threshold": self.processing.min_score_threshold,
                "max_clips_per_collection": self.processing.max_clips_per_collection
            },
            "speech_recognition": {
                "method": self.speech_recognition.method,
                "language": self.speech_recognition.language,
                "model": self.speech_recognition.model
            },
            "bilibili": {
                "auto_upload": self.bilibili.auto_upload,
                "default_tid": self.bilibili.default_tid,
                "max_concurrent_uploads": self.bilibili.max_concurrent_uploads
            },
            "logging": {
                "level": self.logging.level,
                "file": self.logging.file
            },
            "paths": {
                "data_dir": str(self.paths.data_dir),
                "uploads_dir": str(self.paths.uploads_dir),
                "output_dir": str(self.paths.output_dir),
                "temp_dir": str(self.paths.temp_dir)
            }
        }
    
    def validate_config(self) -> Dict[str, Any]:
        """Verification configuration"""
        issues = []
        
        # Validate API configuration
        if not self.api.dashscope_api_key:
            issues.append("DashScope APIKey not configured")
        
        # Validation path
        for path_name, path_value in self.paths.__dict__.items():
            if isinstance(path_value, Path) and not path_value.exists():
                issues.append(f"Path does not exist: {path_name} = {path_value}")
        
        # Validate database connection
        if not self.database.url:
            issues.append("Database URL not configured")
        
        # Verifies Redis connection
        if not self.redis.url:
            issues.append("Redis URLNot configured")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }


# Global configuration instance
config = UnifiedConfig()


# Convenience function
def get_config() -> UnifiedConfig:
    """Get global configuration instance"""
    return config


def get_database_url() -> str:
    """Get databaseURL"""
    return config.database.url


def get_redis_url() -> str:
    """ObtainRedis URL"""
    return config.redis.url


def get_api_key() -> str:
    """Get API key"""
    return config.api.dashscope_api_key


def get_data_directory() -> Path:
    """Get data directory"""
    return config.paths.data_dir


def get_uploads_directory() -> Path:
    """Get upload directory"""
    return config.paths.uploads_dir


def get_output_directory() -> Path:
    """Get output directory"""
    return config.paths.output_dir


def get_temp_directory() -> Path:
    """Get temporary directory"""
    return config.paths.temp_dir


def get_prompt_directory() -> Path:
    """Get prompt directory"""
    return config.paths.prompt_dir


def update_api_key(api_key: str):
    """Update API key"""
    config.api.dashscope_api_key = api_key
    config._setup_environment()
    config.save_to_file()


def update_processing_config(**kwargs):
    """Update processing configuration"""
    config.update_config(processing=kwargs)


def update_bilibili_config(**kwargs):
    """Update Bilibili configuration"""
    config.update_config(bilibili=kwargs)
