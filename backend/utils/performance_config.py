"""
Performance configuration and optimization settings
Provide system performance configuration and optimization parameters
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from enum import Enum


class PerformanceLevel(Enum):
    """Performance level"""
    LOW = "low"          # Low performance, suitable for resource-constrained environments
    MEDIUM = "medium"    # Moderate performance, balancing performance and resource usage
    HIGH = "high"        # High performance, suitable for environments with abundant resources
    CUSTOM = "custom"    # Custom configuration


class FileUploadConfig(BaseModel):
    """File upload configuration"""
    # Multipart upload configuration
    chunk_size: int = Field(default=2 * 1024 * 1024, description="Chunk size (bytes))")  # 2MB
    max_file_size: int = Field(default=2 * 1024 * 1024 * 1024, description="Maximum file size (bytes))")  # 2GB
    max_concurrent_uploads: int = Field(default=3, description="Maximum concurrent uploads")
    upload_timeout: int = Field(default=1800, description="Upload timeout (seconds))")  # 30Minutes
    
    # Retry configuration
    max_retries: int = Field(default=3, description="Maximum number of retries")
    retry_delay: int = Field(default=5, description="Retry delay (seconds))")
    
    # Supported formats
    supported_video_formats: list = Field(
        default=['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'],
        description="Supported video formats"
    )
    supported_subtitle_formats: list = Field(
        default=['.srt', '.vtt', '.ass', '.ssa'],
        description="Subtitle formats"
    )
    
    @validator('chunk_size')
    def validate_chunk_size(cls, v):
        if v <= 0 or v > 10 * 1024 * 1024:  # Max10MB
            raise ValueError('The chunk size must be between 1 byte and 10 MB')
        return v
    
    @validator('max_file_size')
    def validate_max_file_size(cls, v):
        if v <= 0 or v > 10 * 1024 * 1024 * 1024:  # Max10GB
            raise ValueError('The maximum file size must be between 1 byte and 10 GB')
        return v


class ProcessingConfig(BaseModel):
    """Processing configuration"""
    # Concurrency control
    max_concurrent_tasks: int = Field(default=2, description="Maximum concurrent processing tasks")
    max_concurrent_workers: int = Field(default=4, description="Maximum number of concurrent worker processes")
    
    # Memory control
    max_memory_usage: int = Field(default=4 * 1024 * 1024 * 1024, description="Maximum memory usage (bytes))")  # 4GB
    memory_check_interval: int = Field(default=30, description="Memory check interval (seconds))")
    
    # Processing timeout
    video_processing_timeout: int = Field(default=3600, description="Video processing timeout (seconds))")  # 1Hours
    audio_processing_timeout: int = Field(default=1800, description="Audio processing timeout (seconds))")  # 30Minutes
    ai_processing_timeout: int = Field(default=300, description="AIProcessing timeout (seconds))")  # 5Minutes
    
    # Batch processing configuration
    batch_size: int = Field(default=10, description="Batch size")
    batch_timeout: int = Field(default=600, description="Batch timeout (seconds))")  # 10Minutes
    
    @validator('max_concurrent_tasks')
    def validate_max_concurrent_tasks(cls, v):
        if v <= 0 or v > 10:
            raise ValueError('The maximum concurrent task count must be between 1 and 10')
        return v


class CacheConfig(BaseModel):
    """Cache configuration"""
    # Cache size
    max_cache_size: int = Field(default=1024 * 1024 * 1024, description="Maximum cache size (bytes))")  # 1GB
    cache_ttl: int = Field(default=3600, description="Cache time-to-live (seconds))")  # 1Hours
    
    # Caching strategy
    enable_file_cache: bool = Field(default=True, description="Enable file cache")
    enable_result_cache: bool = Field(default=True, description="Enable result cache")
    enable_metadata_cache: bool = Field(default=True, description="Enable metadata cache")
    
    # Cleanup strategy
    cache_cleanup_interval: int = Field(default=1800, description="Cache cleanup interval (seconds))")  # 30Minutes
    cache_cleanup_threshold: float = Field(default=0.8, description="Cache clean threshold")  # 80%


class DatabaseConfig(BaseModel):
    """Database configuration"""
    # Connection pool configuration
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Maximum overflow connection count")
    pool_timeout: int = Field(default=30, description="Connection pool timeout (seconds))")
    pool_recycle: int = Field(default=3600, description="Connection recycling time (seconds))")
    
    # Query optimization
    query_timeout: int = Field(default=30, description="Query timeout (seconds))")
    enable_query_cache: bool = Field(default=True, description="Enable query caching")
    
    @validator('pool_size')
    def validate_pool_size(cls, v):
        if v <= 0 or v > 100:
            raise ValueError('The connection pool size must be between 1 and 100')
        return v


class PerformanceConfig(BaseModel):
    """Performance configuration class"""
    level: PerformanceLevel = Field(default=PerformanceLevel.MEDIUM, description="Performance level")
    
    # Subconfiguration
    file_upload: FileUploadConfig = Field(default_factory=FileUploadConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    
    # Global settings
    enable_monitoring: bool = Field(default=True, description="Enable performance monitoring")
    monitoring_interval: int = Field(default=60, description="Monitor interval (seconds))")
    log_performance_metrics: bool = Field(default=True, description="Record performance metrics")
    
    def get_config_for_level(self, level: PerformanceLevel) -> 'PerformanceConfig':
        """Get configurations by performance level"""
        if level == PerformanceLevel.LOW:
            return self._get_low_performance_config()
        elif level == PerformanceLevel.MEDIUM:
            return self._get_medium_performance_config()
        elif level == PerformanceLevel.HIGH:
            return self._get_high_performance_config()
        else:
            return self
    
    def _get_low_performance_config(self) -> 'PerformanceConfig':
        """Low-performance configuration"""
        return PerformanceConfig(
            level=PerformanceLevel.LOW,
            file_upload=FileUploadConfig(
                chunk_size=1024 * 1024,  # 1MB
                max_file_size=512 * 1024 * 1024,  # 512MB
                max_concurrent_uploads=1,
                upload_timeout=900,  # 15Minutes
                max_retries=2
            ),
            processing=ProcessingConfig(
                max_concurrent_tasks=1,
                max_concurrent_workers=2,
                max_memory_usage=2 * 1024 * 1024 * 1024,  # 2GB
                video_processing_timeout=1800,  # 30Minutes
                audio_processing_timeout=900,  # 15Minutes
                ai_processing_timeout=180  # 3Minutes
            ),
            cache=CacheConfig(
                max_cache_size=256 * 1024 * 1024,  # 256MB
                cache_ttl=1800,  # 30Minutes
                enable_file_cache=False,
                enable_result_cache=True,
                enable_metadata_cache=True
            ),
            database=DatabaseConfig(
                pool_size=5,
                max_overflow=10,
                enable_query_cache=False
            )
        )
    
    def _get_medium_performance_config(self) -> 'PerformanceConfig':
        """Medium performance configuration"""
        return PerformanceConfig(
            level=PerformanceLevel.MEDIUM,
            file_upload=FileUploadConfig(
                chunk_size=2 * 1024 * 1024,  # 2MB
                max_file_size=2 * 1024 * 1024 * 1024,  # 2GB
                max_concurrent_uploads=3,
                upload_timeout=1800,  # 30Minutes
                max_retries=3
            ),
            processing=ProcessingConfig(
                max_concurrent_tasks=2,
                max_concurrent_workers=4,
                max_memory_usage=4 * 1024 * 1024 * 1024,  # 4GB
                video_processing_timeout=3600,  # 1Hours
                audio_processing_timeout=1800,  # 30Minutes
                ai_processing_timeout=300  # 5Minutes
            ),
            cache=CacheConfig(
                max_cache_size=1024 * 1024 * 1024,  # 1GB
                cache_ttl=3600,  # 1Hours
                enable_file_cache=True,
                enable_result_cache=True,
                enable_metadata_cache=True
            ),
            database=DatabaseConfig(
                pool_size=10,
                max_overflow=20,
                enable_query_cache=True
            )
        )
    
    def _get_high_performance_config(self) -> 'PerformanceConfig':
        """High-performance configuration"""
        return PerformanceConfig(
            level=PerformanceLevel.HIGH,
            file_upload=FileUploadConfig(
                chunk_size=4 * 1024 * 1024,  # 4MB
                max_file_size=5 * 1024 * 1024 * 1024,  # 5GB
                max_concurrent_uploads=5,
                upload_timeout=3600,  # 1Hours
                max_retries=5
            ),
            processing=ProcessingConfig(
                max_concurrent_tasks=4,
                max_concurrent_workers=8,
                max_memory_usage=8 * 1024 * 1024 * 1024,  # 8GB
                video_processing_timeout=7200,  # 2Hours
                audio_processing_timeout=3600,  # 1Hours
                ai_processing_timeout=600  # 10Minutes
            ),
            cache=CacheConfig(
                max_cache_size=2 * 1024 * 1024 * 1024,  # 2GB
                cache_ttl=7200,  # 2Hours
                enable_file_cache=True,
                enable_result_cache=True,
                enable_metadata_cache=True
            ),
            database=DatabaseConfig(
                pool_size=20,
                max_overflow=40,
                enable_query_cache=True
            )
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "level": self.level.value,
            "file_upload": self.file_upload.dict(),
            "processing": self.processing.dict(),
            "cache": self.cache.dict(),
            "database": self.database.dict(),
            "enable_monitoring": self.enable_monitoring,
            "monitoring_interval": self.monitoring_interval,
            "log_performance_metrics": self.log_performance_metrics
        }


# Global performance configuration instance
performance_config = PerformanceConfig()

# Performance level configuration mapping
PERFORMANCE_LEVELS = {
    PerformanceLevel.LOW: performance_config._get_low_performance_config(),
    PerformanceLevel.MEDIUM: performance_config._get_medium_performance_config(),
    PerformanceLevel.HIGH: performance_config._get_high_performance_config(),
}


def get_performance_config(level: PerformanceLevel = PerformanceLevel.MEDIUM) -> PerformanceConfig:
    """Retrieve performance configuration by level"""
    return PERFORMANCE_LEVELS.get(level, performance_config._get_medium_performance_config())


def update_performance_config(config_dict: Dict[str, Any]) -> PerformanceConfig:
    """Update performance configuration"""
    global performance_config
    
    # Update configuration
    if 'level' in config_dict:
        level = PerformanceLevel(config_dict['level'])
        performance_config = performance_config.get_config_for_level(level)
    
    # Update child configuration
    if 'file_upload' in config_dict:
        performance_config.file_upload = FileUploadConfig(**config_dict['file_upload'])
    
    if 'processing' in config_dict:
        performance_config.processing = ProcessingConfig(**config_dict['processing'])
    
    if 'cache' in config_dict:
        performance_config.cache = CacheConfig(**config_dict['cache'])
    
    if 'database' in config_dict:
        performance_config.database = DatabaseConfig(**config_dict['database'])
    
    # Update global settings
    if 'enable_monitoring' in config_dict:
        performance_config.enable_monitoring = config_dict['enable_monitoring']
    
    if 'monitoring_interval' in config_dict:
        performance_config.monitoring_interval = config_dict['monitoring_interval']
    
    if 'log_performance_metrics' in config_dict:
        performance_config.log_performance_metrics = config_dict['log_performance_metrics']
    
    return performance_config
