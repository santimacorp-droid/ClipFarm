"""
Hierarchical error handling system - provides unified error handling, retry mechanism, and circuit breaker
"""
import logging
import time
import functools
from typing import Type, Callable, Any, Optional, Dict, List
from enum import Enum
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class ErrorLevel(Enum):
    """Error level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ErrorCategory(Enum):
    """Error classification enumeration"""
    CONFIGURATION = "CONFIGURATION"
    NETWORK = "NETWORK"
    API = "API"
    FILE_IO = "FILE_IO"
    PROCESSING = "PROCESSING"
    VALIDATION = "VALIDATION"
    SYSTEM = "SYSTEM"

class AutoClipsException(Exception):
    """Auto-slicing tool base exception class"""
    
    def __init__(self, message: str, category: ErrorCategory, level: ErrorLevel = ErrorLevel.ERROR, 
                 details: Optional[Dict[str, Any]] = None, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.level = level
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = time.time()
    
    def __str__(self):
        return f"[{self.category.value}] {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "message": self.message,
            "category": self.category.value,
            "level": self.level.value,
            "details": self.details,
            "timestamp": self.timestamp,
            "original_exception": str(self.original_exception) if self.original_exception else None
        }

class ConfigurationError(AutoClipsException):
    """Configuration error"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.CONFIGURATION, ErrorLevel.ERROR, details)

class NetworkError(AutoClipsException):
    """Network error"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.NETWORK, ErrorLevel.ERROR, details, original_exception)

class APIError(AutoClipsException):
    """APIInvocation error"""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        api_details = details or {}
        if status_code:
            api_details["status_code"] = status_code
        super().__init__(message, ErrorCategory.API, ErrorLevel.ERROR, api_details)

class FileIOError(AutoClipsException):
    """File I/O error"""
    def __init__(self, message: str, file_path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        file_details = details or {}
        if file_path:
            file_details["file_path"] = file_path
        super().__init__(message, ErrorCategory.FILE_IO, ErrorLevel.ERROR, file_details)

class ProcessingError(AutoClipsException):
    """Error handling"""
    def __init__(self, message: str, step: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        processing_details = details or {}
        if step:
            processing_details["step"] = step
        super().__init__(message, ErrorCategory.PROCESSING, ErrorLevel.ERROR, processing_details)

class ValidationError(AutoClipsException):
    """Validation error"""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        validation_details = details or {}
        if field:
            validation_details["field"] = field
        super().__init__(message, ErrorCategory.VALIDATION, ErrorLevel.WARNING, validation_details)

@dataclass
class RetryConfig:
    """Retry configuration"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: List[Type[Exception]] = None
    
    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [
                NetworkError,
                APIError,
                ConnectionError,
                TimeoutError,
                OSError
            ]

class CircuitBreaker:
    """Circuit breaker implementation"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0, 
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function, apply circuit breaker logic"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise AutoClipsException(
                    "Circuit breaker is open, reject execution",
                    ErrorCategory.SYSTEM,
                    ErrorLevel.WARNING
                )
        
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            
            raise e

def retry_with_backoff(config: Optional[RetryConfig] = None):
    """Retry decorator, supports exponential backoff"""
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(config.retryable_exceptions) as e:
                    last_exception = e
                    
                    if attempt == config.max_retries:
                        logger.error(f"Function {func.__name__} In {config.max_retries} Failed after the second attempt: {e}")
                        raise e
                    
                    # Calculate delay time
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    logger.warning(f"Function {func.__name__} The {attempt + 1} Attempt failed, {delay}Retry in seconds: {e}")
                    time.sleep(delay)
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator

@contextmanager
def error_context(category: ErrorCategory, context_info: Optional[Dict[str, Any]] = None):
    """Error context manager"""
    try:
        yield
    except Exception as e:
        if isinstance(e, AutoClipsException):
            # Already a custom exception, re-raise
            raise
        else:
            # Convert to custom exception
            details = context_info or {}
            details["original_exception_type"] = type(e).__name__
            
            if category == ErrorCategory.API:
                raise APIError(str(e), details=details)
            elif category == ErrorCategory.NETWORK:
                raise NetworkError(str(e), details=details, original_exception=e)
            elif category == ErrorCategory.FILE_IO:
                raise FileIOError(str(e), details=details)
            elif category == ErrorCategory.PROCESSING:
                raise ProcessingError(str(e), details=details)
            elif category == ErrorCategory.VALIDATION:
                raise ValidationError(str(e), details=details)
            else:
                raise AutoClipsException(str(e), category, details=details, original_exception=e)

class ErrorHandler:
    """Error handler"""
    
    def __init__(self):
        self.error_log: List[AutoClipsException] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def handle_error(self, error: AutoClipsException, context: Optional[str] = None):
        """Error handling"""
        # Log error
        self.error_log.append(error)
        
        # Log by error level
        if error.level == ErrorLevel.DEBUG:
            logger.debug(f"[{context}] {error}")
        elif error.level == ErrorLevel.INFO:
            logger.info(f"[{context}] {error}")
        elif error.level == ErrorLevel.WARNING:
            logger.warning(f"[{context}] {error}")
        elif error.level == ErrorLevel.ERROR:
            logger.error(f"[{context}] {error}")
        elif error.level == ErrorLevel.CRITICAL:
            logger.critical(f"[{context}] {error}")
        
        # Special processing based on error classification
        if error.category == ErrorCategory.API and isinstance(error, APIError):
            self._handle_api_error(error)
        elif error.category == ErrorCategory.NETWORK and isinstance(error, NetworkError):
            self._handle_network_error(error)
        elif error.category == ErrorCategory.CONFIGURATION and isinstance(error, ConfigurationError):
            self._handle_configuration_error(error)
    
    def _handle_api_error(self, error: APIError):
        """Handle API errors"""
        # Add specific API error handling logic here
        # For example: update API key, switch to backup API, etc.
        pass
    
    def _handle_network_error(self, error: NetworkError):
        """Handling network errors"""
        # Add specific network error handling logic here
        # For example: switch network, retry connection, etc.
        pass
    
    def _handle_configuration_error(self, error: ConfigurationError):
        """Processing configuration error"""
        # Add specific configuration error handling logic here
        # For example: load default configuration, prompt user to fix, etc.
        pass
    
    def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(**kwargs)
        return self.circuit_breakers[name]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary"""
        if not self.error_log:
            return {"total_errors": 0}
        
        error_counts = {}
        for error in self.error_log:
            category = error.category.value
            error_counts[category] = error_counts.get(category, 0) + 1
        
        return {
            "total_errors": len(self.error_log),
            "error_counts": error_counts,
            "latest_error": self.error_log[-1].to_dict() if self.error_log else None
        }
    
    def clear_error_log(self):
        """Clear error log"""
        self.error_log.clear()

# Global error handler instance
error_handler = ErrorHandler()

def safe_execute(func: Callable, *args, context: Optional[str] = None, 
                retry_config: Optional[RetryConfig] = None, **kwargs) -> Any:
    """Secure function execution with error handling and retry"""
    if retry_config:
        func = retry_with_backoff(retry_config)(func)
    
    try:
        return func(*args, **kwargs)
    except AutoClipsException as e:
        error_handler.handle_error(e, context)
        raise
    except Exception as e:
        # Convert to generic exception
        auto_clips_error = AutoClipsException(
            str(e), 
            ErrorCategory.SYSTEM, 
            ErrorLevel.ERROR,
            original_exception=e
        )
        error_handler.handle_error(auto_clips_error, context)
        raise auto_clips_error 