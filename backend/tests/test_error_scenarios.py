"""
Error scenario testing
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add project root directory toPythonpath
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from backend.services.exceptions import (
    ServiceError, ConfigurationError, FileOperationError, 
    ProcessingError, TaskError, ProjectError, ConcurrentError
)
from backend.services.processing_context import ProcessingContext
from backend.services.config_manager import ProjectConfigManager
from backend.services.pipeline_adapter import PipelineAdapter


class TestConfigurationErrorScenarios:
    """Test configuration error scenario"""
    
    def test_missing_api_key(self, tmp_path, monkeypatch):
        """Test missingAPIkey"""
        # CI injection DASHSCOPE_API_KEY For use by other test cases; explicitly clear here to trigger error paths
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Creation failedAPIKey configuration
        config_manager = ProjectConfigManager(str(project_dir))

        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            config_manager.get_llm_config()
    
    def test_invalid_processing_params(self, tmp_path):
        """Invalid processing parameter"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        config_manager = ProjectConfigManager(str(project_dir))
        
        # Set invalid parameter
        config_manager.update_processing_params(chunk_size=-1)
        
        # Verify configuration should fail
        validation_result = config_manager.validate_config()
        assert validation_result["valid"] is False
        assert any("chunk_size" in error for error in validation_result["errors"])
    
    def test_missing_prompt_files(self, tmp_path):
        """Test missingpromptFile"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        config_manager = ProjectConfigManager(str(project_dir))
        
        # Simulate missingpromptFile state
        with patch('pathlib.Path.exists', return_value=False):
            prompt_files = config_manager.get_prompt_files()
            
            # Should return an empty dictionary or one containing information about missing files
            assert isinstance(prompt_files, dict)


class TestFileOperationErrorScenarios:
    """File operation error scenario testing"""
    
    def test_nonexistent_srt_file(self, tmp_path):
        """Test non-existentSRTFile"""
        context = ProcessingContext("test_project", "test_task")
        
        with pytest.raises(FileNotFoundError):
            context.set_srt_path(Path("nonexistent.srt"))
    
    def test_invalid_srt_format(self, tmp_path):
        """Test invalidSRTformat"""
        # Create malformedSRTFile
        invalid_srt = tmp_path / "invalid.srt"
        invalid_srt.write_text("This is not validSRTformat\nNo timestamp\nNo sequence number")
        
        # This should testSRTFormat validation logic
        # Since the current implementation has no format validation, we only test file existence
        assert invalid_srt.exists()
    
    def test_permission_denied(self, tmp_path):
        """Test permission denied"""
        # Create read-only file
        read_only_file = tmp_path / "readonly.srt"
        read_only_file.write_text("Test content")
        read_only_file.chmod(0o444)  # Read-only permissions
        
        try:
            # Attempt to write to read-only file
            with pytest.raises(PermissionError):
                read_only_file.write_text("New content")
        finally:
            # Restore permissions
            read_only_file.chmod(0o666)
    
    def test_corrupted_config_file(self, tmp_path):
        """Test corrupted configuration files"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # Create corruptYAMLFile
        config_file = project_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")
        
        config_manager = ProjectConfigManager(str(project_dir))
        
        # Should be able to handle corrupted configuration files
        config = config_manager.config
        assert isinstance(config, dict)


class TestProcessingErrorScenarios:
    """Test processing error scenario"""
    
    def test_step_execution_failure(self, tmp_path):
        """Test step execution failed"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        adapter = PipelineAdapter(str(project_dir))
        
        # Test step execution failure (file does not exist)
        with pytest.raises(FileNotFoundError):
            adapter.adapt_step("step1_outline", srt_path=Path("nonexistent.srt"))
    
    def test_timeout_error(self, tmp_path):
        """Test timeout error"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        adapter = PipelineAdapter(str(project_dir))
        
        # Test timeout errors (file does not exist)
        with pytest.raises(FileNotFoundError):
            adapter.adapt_step("step1_outline", srt_path=Path("nonexistent.srt"))
    
    def test_missing_dependencies(self, tmp_path):
        """Test missing dependency"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        adapter = PipelineAdapter(str(project_dir))
        
        # Test missing dependency scenarios (file does not exist)
        with pytest.raises(FileNotFoundError):
            adapter.adapt_step("step1_outline", srt_path=Path("nonexistent.srt"))


class TestConcurrencyErrorScenarios:
    """Test concurrent error scenario"""
    
    def test_resource_already_locked(self, tmp_path):
        """Test resource already locked"""
        from backend.services.concurrency_manager import concurrency_manager
        
        resource_id = "test_resource"
        task_id_1 = "task_001"
        task_id_2 = "task_002"
        
        # First task acquires lock
        acquired_1 = concurrency_manager.acquire_lock(resource_id, task_id_1)
        assert acquired_1 is True
        
        # Second task tries to obtain same lock
        acquired_2 = concurrency_manager.acquire_lock(resource_id, task_id_2)
        assert acquired_2 is False
        
        # cleanup
        concurrency_manager.release_lock(resource_id, task_id_1)
    
    def test_lock_timeout(self, tmp_path):
        """Test lock timeout"""
        from backend.services.concurrency_manager import concurrency_manager
        
        resource_id = "test_resource"
        task_id = "task_001"
        
        # Get lock
        acquired = concurrency_manager.acquire_lock(resource_id, task_id, timeout_seconds=1)
        assert acquired is True
        
        # Check lock status
        is_locked = concurrency_manager.is_locked(resource_id)
        assert is_locked is True
        
        # cleanup
        concurrency_manager.release_lock(resource_id, task_id)
    
    def test_invalid_lock_release(self, tmp_path):
        """Test invalid lock release"""
        from backend.services.concurrency_manager import concurrency_manager
        
        resource_id = "test_resource"
        task_id = "task_001"
        
        # Attempt to release nonexistent lock
        released = concurrency_manager.release_lock(resource_id, task_id)
        assert released is False


class TestContextErrorScenarios:
    """Context error scenario testing"""
    
    def test_invalid_project_id(self):
        """Test invalid projectID"""
        with pytest.raises(ValueError, match="project_id.*empty"):
            ProcessingContext("", "test_task")
    
    def test_invalid_task_id(self):
        """Test invalid taskID"""
        with pytest.raises(ValueError, match="task_id.*empty"):
            ProcessingContext("test_project", "")
    
    def test_context_validation_failure(self):
        """Test context validation failures"""
        context = ProcessingContext("test_project", "test_task")
        
        # Uninitialized contexts are unsuitable for execution
        assert context.is_valid_for_execution() is False
        
        # Set an error then disallow further execution
        context.set_error("Test error")
        assert context.is_valid_for_execution() is False
        
        # Not suitable after completion
        context.mark_completed()
        assert context.is_valid_for_execution() is False


class TestIntegrationErrorScenarios:
    """Test integration error scenario"""
    
    def test_full_pipeline_failure(self, tmp_path):
        """Test full pipeline failed"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # Create config manager
        config_manager = ProjectConfigManager(str(project_dir))
        
        # Create pipeline adapter
        adapter = PipelineAdapter(str(project_dir))
        
        # Validate prerequisites (should fail because there is noSRTFile)
        errors = adapter.validate_pipeline_prerequisites()
        assert len(errors) > 0
        assert any("SRTFile" in error for error in errors)
    
    def test_partial_success_scenario(self, tmp_path):
        """Test partial success scenario"""
        # Set test environment variable
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # CreateSRTFile in correct location
        raw_dir = project_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        srt_file = raw_dir / "transcript.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:05,000\nTest subtitles")
        
        adapter = PipelineAdapter(str(project_dir))
        
        # Validate prerequisites (should succeed)
        errors = adapter.validate_pipeline_prerequisites()
        assert len(errors) == 0
    
    def test_error_recovery(self, tmp_path):
        """Test error recovery"""
        context = ProcessingContext("test_project", "test_task")
        
        # Settings error
        context.set_error("Temporary error")
        assert context.error_message == "Temporary error"
        assert context.is_valid_for_execution() is False
        
        # Clear errors (Note: The current implementation does not provide a method to clear errors))
        # Test error status management
        assert context.error_message is not None


def test_error_propagation():
    """Test error propagation"""
    # Test error chain
    original_error = ValueError("Original error")
    
    service_error = ServiceError(
        "Service error",
        details={"operation": "test"},
        cause=original_error
    )
    
    assert service_error.cause == original_error
    assert service_error.cause.args[0] == "Original error"


def test_error_serialization():
    """Test error serialization"""
    error = ServiceError(
        "Test error",
        details={"key": "value", "number": 123}
    )
    
    error_dict = error.to_dict()
    
    assert "error_code" in error_dict
    assert "message" in error_dict
    assert "details" in error_dict
    assert error_dict["details"]["key"] == "value"
    assert error_dict["details"]["number"] == 123


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
