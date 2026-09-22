"""
Service exception hierarchy
Unified exception handling mechanism
"""

import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Error code enumeration"""
    # Configuration-related errors
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING_REQUIRED = "CONFIG_MISSING_REQUIRED"
    
    # File-related errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_PERMISSION_DENIED = "FILE_PERMISSION_DENIED"
    FILE_CORRUPTED = "FILE_CORRUPTED"
    
    # Processing-related errors
    PROCESSING_FAILED = "PROCESSING_FAILED"
    STEP_EXECUTION_FAILED = "STEP_EXECUTION_FAILED"
    PIPELINE_VALIDATION_FAILED = "PIPELINE_VALIDATION_FAILED"
    
    # Task-related errors
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_ALREADY_RUNNING = "TASK_ALREADY_RUNNING"
    TASK_CANCELLED = "TASK_CANCELLED"
    
    # Project-related errors
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    PROJECT_ALREADY_EXISTS = "PROJECT_ALREADY_EXISTS"
    
    # System-related errors
    SYSTEM_ERROR = "SYSTEM_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    
    # Concurrency-related errors
    CONCURRENT_ACCESS = "CONCURRENT_ACCESS"
    LOCK_ACQUISITION_FAILED = "LOCK_ACQUISITION_FAILED"
    
    # Unknown error
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ServiceError(Exception):
    """Base class for service exceptions"""
    
    def __init__(self, 
                 message: str,
                 error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
                 details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.timestamp = None  # Will be set in subclasses
        
        # Log error messages
        self._log_error()
    
    def _log_error(self):
        """Log error messages"""
        log_message = f"ServiceError: {self.error_code.value} - {self.message}"
        if self.details:
            log_message += f" | Details: {self.details}"
        if self.cause:
            log_message += f" | Cause: {self.cause}"
        
        logger.error(log_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class ConfigurationError(ServiceError):
    """Configuration-related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(message, ErrorCode.CONFIG_INVALID, details, cause)


class FileOperationError(ServiceError):
    """File operation related errors"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if file_path:
            details = details or {}
            details["file_path"] = file_path
        super().__init__(message, ErrorCode.FILE_NOT_FOUND, details, cause)


class ProcessingError(ServiceError):
    """Processing-related errors"""
    
    def __init__(self, message: str, step_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if step_name:
            details = details or {}
            details["step_name"] = step_name
        super().__init__(message, ErrorCode.PROCESSING_FAILED, details, cause)


class TaskError(ServiceError):
    """Task-related errors"""
    
    def __init__(self, message: str, task_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if task_id:
            details = details or {}
            details["task_id"] = task_id
        super().__init__(message, ErrorCode.TASK_NOT_FOUND, details, cause)


class ProjectError(ServiceError):
    """Project-related errors"""
    
    def __init__(self, message: str, project_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if project_id:
            details = details or {}
            details["project_id"] = project_id
        super().__init__(message, ErrorCode.PROJECT_NOT_FOUND, details, cause)


class ConcurrentError(ServiceError):
    """Concurrency-related errors"""
    
    def __init__(self, message: str, resource: Optional[str] = None, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        if resource:
            details = details or {}
            details["resource"] = resource
        super().__init__(message, ErrorCode.CONCURRENT_ACCESS, details, cause)


class SystemError(ServiceError):
    """System-related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(message, ErrorCode.SYSTEM_ERROR, details, cause)


def handle_service_error(func):
    """Service error handling decorator"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceError:
            # Reraise ServiceError
            raise
        except Exception as e:
            # Wrap other exceptions as ServiceError
            logger.error(f"Unhandled exceptions: {e}")
            raise SystemError(f"System error: {str(e)}", cause=e)
    return wrapper


def create_error_response(error: ServiceError) -> Dict[str, Any]:
    """Create error response"""
    return {
        "success": False,
        "error": error.to_dict()
    }


def is_service_error(exception: Exception) -> bool:
    """Check if it is a service exception"""
    return isinstance(exception, ServiceError) 