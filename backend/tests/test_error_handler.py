"""
Error handling system unit test
"""
import time
from unittest.mock import patch, MagicMock

import pytest
from backend.utils.error_handler import (
    AutoClipsException, APIError, NetworkError, ConfigurationError,
    FileIOError, ProcessingError, ValidationError,
    ErrorLevel, ErrorCategory, RetryConfig, CircuitBreaker,
    retry_with_backoff, error_context, ErrorHandler, safe_execute
)


class TestAutoClipsException:
    """Test base exception class"""
    
    def test_exception_creation(self):
        """Test exception creation"""
        error = AutoClipsException("Test error", ErrorCategory.API)
        assert error.message == "Test error"
        assert error.category == ErrorCategory.API
        assert error.level == ErrorLevel.ERROR
        assert error.timestamp > 0
    
    def test_exception_to_dict(self):
        """Test exception to dictionary"""
        original_exception = ValueError("Original error")
        error = AutoClipsException(
            "Test error", 
            ErrorCategory.API, 
            ErrorLevel.WARNING,
            {"detail": "Details"},
            original_exception
        )
        
        error_dict = error.to_dict()
        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "API"
        assert error_dict["level"] == "WARNING"
        assert error_dict["details"]["detail"] == "Details"
        assert "Original error" in error_dict["original_exception"]
    
    def test_exception_str_representation(self):
        """Test exception string representation"""
        error = AutoClipsException("Test error", ErrorCategory.NETWORK)
        assert str(error) == "[NETWORK] Test error"


class TestSpecificExceptions:
    """Test specific exception class"""
    
    def test_api_error(self):
        """TestAPIError"""
        error = APIError("APICall failed", status_code=400)
        assert error.category == ErrorCategory.API
        assert error.details["status_code"] == 400
    
    def test_network_error(self):
        """Test network error"""
        original_exception = ConnectionError("Connection failed")
        error = NetworkError("Network error", original_exception=original_exception)
        assert error.category == ErrorCategory.NETWORK
        assert error.original_exception == original_exception
    
    def test_file_io_error(self):
        """Test fileIOError"""
        error = FileIOError("File read failure", file_path="/test/file.txt")
        assert error.category == ErrorCategory.FILE_IO
        assert error.details["file_path"] == "/test/file.txt"
    
    def test_processing_error(self):
        """Test handle error"""
        error = ProcessingError("Processing failed", step="Step 1")
        assert error.category == ErrorCategory.PROCESSING
        assert error.details["step"] == "Step 1"
    
    def test_validation_error(self):
        """Test verification failed"""
        error = ValidationError("Verification failed", field="api_key")
        assert error.category == ErrorCategory.VALIDATION
        assert error.level == ErrorLevel.WARNING
        assert error.details["field"] == "api_key"


class TestRetryConfig:
    """Test retry configuration"""
    
    def test_retry_config_defaults(self):
        """Test default retry configuration values"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert len(config.retryable_exceptions) > 0
    
    def test_retry_config_custom_values(self):
        """Test custom retry configuration values"""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0
        )
        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0


class TestCircuitBreaker:
    """Circuit breaker test"""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initial state"""
        cb = CircuitBreaker()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
    
    def test_circuit_breaker_successful_call(self):
        """Test successful circuit breaker invocation"""
        cb = CircuitBreaker()
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == "CLOSED"
    
    def test_circuit_breaker_failure_threshold(self):
        """Test failure threshold"""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_func():
            raise ValueError("Test failed")
        
        # First failure
        with patch('time.time', return_value=1000):
            with pytest.raises(ValueError):
                cb.call(failing_func)
            assert cb.state == "CLOSED"
            assert cb.failure_count == 1
        
        # Second failure triggers circuit break
        with patch('time.time', return_value=1001):
            with pytest.raises(ValueError):
                cb.call(failing_func)
            assert cb.state == "OPEN"
            assert cb.failure_count == 2
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery"""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
        
        def failing_func():
            raise ValueError("Test failed")
        
        # Trigger circuit breaker
        with patch('time.time', return_value=1000):
            with pytest.raises(ValueError):
                cb.call(failing_func)
            assert cb.state == "OPEN"
        
        # Wait time elapsed, status changed to half-open
        with patch('time.time', return_value=1002):  # Exceeded recovery time
            def success_func():
                return "success"
            
            result = cb.call(success_func)
            assert result == "success"
            assert cb.state == "CLOSED"  # Close after success


class TestRetryDecorator:
    """Test retry decorator"""
    
    def test_retry_success_on_first_try(self):
        """Test success on first try"""
        @retry_with_backoff()
        def success_func():
            return "success"
        
        result = success_func()
        assert result == "success"
    
    def test_retry_success_after_failures(self):
        """Test successful retry after failure"""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=2, base_delay=0.1))
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network error")
            return "success"
        
        result = failing_then_success()
        assert result == "success"
        assert call_count == 3
    
    def test_retry_max_attempts_exceeded(self):
        """Test exceeded maximum retry count"""
        @retry_with_backoff(RetryConfig(max_retries=1, base_delay=0.1))
        def always_failing():
            raise APIError("APIError")
        
        with pytest.raises(APIError):
            always_failing()


class TestErrorContext:
    """Test error context manager"""
    
    def test_error_context_no_exception(self):
        """Test without exceptions"""
        with error_context(ErrorCategory.API):
            result = "success"
        
        assert result == "success"
    
    def test_error_context_with_exception(self):
        """Test with exceptions"""
        with pytest.raises(APIError):
            with error_context(ErrorCategory.API):
                raise ValueError("Original error")
    
    def test_error_context_preserves_auto_clips_exception(self):
        """Preserved testsAutoClipsException"""
        original_error = APIError("APIError")
        with pytest.raises(APIError) as exc_info:
            with error_context(ErrorCategory.NETWORK):
                raise original_error
        
        assert exc_info.value == original_error


class TestErrorHandler:
    """Test error handler"""
    
    def test_error_handler_initialization(self):
        """Test error processor initialization"""
        handler = ErrorHandler()
        assert len(handler.error_log) == 0
        assert len(handler.circuit_breakers) == 0
    
    def test_error_handler_handle_error(self):
        """Test error handling"""
        handler = ErrorHandler()
        error = APIError("TestAPIError")
        
        with patch('logging.Logger.error') as mock_logger:
            handler.handle_error(error, "Test context")
            
            assert len(handler.error_log) == 1
            assert handler.error_log[0] == error
            mock_logger.assert_called_once()
    
    def test_error_handler_get_circuit_breaker(self):
        """Test get circuit breaker"""
        handler = ErrorHandler()
        
        cb1 = handler.get_circuit_breaker("test")
        cb2 = handler.get_circuit_breaker("test")
        
        assert cb1 is cb2  # Returns same instance for same name
        assert len(handler.circuit_breakers) == 1
    
    def test_error_handler_get_error_summary(self):
        """Test get error summary"""
        handler = ErrorHandler()
        
        # When there are no errors
        summary = handler.get_error_summary()
        assert summary["total_errors"] == 0
        
        # When there's an error
        handler.handle_error(APIError("APIError1"))
        handler.handle_error(NetworkError("Network error"))
        handler.handle_error(APIError("APIError2"))
        
        summary = handler.get_error_summary()
        assert summary["total_errors"] == 3
        assert summary["error_counts"]["API"] == 2
        assert summary["error_counts"]["NETWORK"] == 1
        assert summary["latest_error"] is not None
    
    def test_error_handler_clear_error_log(self):
        """Test clear error logs"""
        handler = ErrorHandler()
        handler.handle_error(APIError("Test error"))
        assert len(handler.error_log) == 1
        
        handler.clear_error_log()
        assert len(handler.error_log) == 0


class TestSafeExecute:
    """Test secure function execution"""
    
    def test_safe_execute_success(self):
        """Test successful execution"""
        def success_func():
            return "success"
        
        result = safe_execute(success_func, context="Test")
        assert result == "success"
    
    def test_safe_execute_with_retry(self):
        """Test execution with retries"""
        call_count = 0
        
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Network error")
            return "success"
        
        retry_config = RetryConfig(max_retries=1, base_delay=0.1)
        result = safe_execute(failing_then_success, context="Test", retry_config=retry_config)
        assert result == "success"
        assert call_count == 2
    
    def test_safe_execute_handles_auto_clips_exception(self):
        """Test handlingAutoClipsException"""
        def raise_auto_clips_error():
            raise APIError("APIError")
        
        with pytest.raises(APIError):
            safe_execute(raise_auto_clips_error, context="Test")
    
    def test_safe_execute_converts_generic_exception(self):
        """Test conversion of generic exception"""
        def raise_generic_error():
            raise ValueError("Generic error")
        
        with pytest.raises(AutoClipsException) as exc_info:
            safe_execute(raise_generic_error, context="Test")
        
        assert exc_info.value.category == ErrorCategory.SYSTEM
        assert "Generic error" in str(exc_info.value)


# Test helper function
def test_error_level_enum():
    """Test error level enumeration"""
    assert ErrorLevel.DEBUG.value == "DEBUG"
    assert ErrorLevel.ERROR.value == "ERROR"
    assert ErrorLevel.CRITICAL.value == "CRITICAL"


def test_error_category_enum():
    """Test error classification enum"""
    assert ErrorCategory.API.value == "API"
    assert ErrorCategory.NETWORK.value == "NETWORK"
    assert ErrorCategory.CONFIGURATION.value == "CONFIGURATION"


if __name__ == '__main__':
    pytest.main([__file__]) 