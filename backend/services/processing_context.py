"""
Processes context
Unifies management of processing-related context
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """Manages processing-related context information in a unified manner"""
    
    project_id: str
    task_id: str
    db_session: Any = None
    srt_path: Optional[Path] = None
    debug_mode: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    # Processing status
    is_initialized: bool = False
    is_completed: bool = False
    error_message: Optional[str] = None
    
    # Configuration information
    config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization handling"""
        self.validate_context()
    
    def validate_context(self):
        """Validates context"""
        if not self.project_id:
            raise ValueError("project_idCannot be empty")
        if not self.task_id:
            raise ValueError("task_idCannot be empty")
        
        logger.debug(f"ProcessingContextValidation passed: project_id={self.project_id}, task_id={self.task_id}")
    
    def set_srt_path(self, srt_path: Path):
        """Sets SRT file path"""
        if not srt_path.exists():
            raise FileNotFoundError(f"SRTFile not found: {srt_path}")
        self.srt_path = srt_path
        logger.debug(f"Sets SRT path: {srt_path}")
    
    def set_debug_mode(self, debug_mode: bool):
        """Enables debug mode"""
        self.debug_mode = debug_mode
        logger.debug(f"Enables debug mode: {debug_mode}")
    
    def set_config(self, config: Dict[str, Any]):
        """Sets configuration information"""
        self.config.update(config)
        logger.debug(f"Updates configuration: {list(config.keys())}")
    
    def mark_initialized(self):
        """Flags as initialized"""
        self.is_initialized = True
        logger.debug("ProcessingContextInitialized")
    
    def mark_completed(self):
        """Flags as complete"""
        self.is_completed = True
        logger.debug("ProcessingContextComplete")
    
    def set_error(self, error_message: str):
        """Sets error message"""
        self.error_message = error_message
        logger.error(f"ProcessingContextError: {error_message}")
    
    def is_valid_for_execution(self) -> bool:
        """Checks suitability for execution"""
        if not self.is_initialized:
            return False
        if self.is_completed:
            return False
        if self.error_message:
            return False
        return True
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Retrieves context summary"""
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "srt_path": str(self.srt_path) if self.srt_path else None,
            "debug_mode": self.debug_mode,
            "is_initialized": self.is_initialized,
            "is_completed": self.is_completed,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "config_keys": list(self.config.keys()) if self.config else []
        }
    
    def clone(self) -> 'ProcessingContext':
        """Clones context"""
        cloned = ProcessingContext(
            project_id=self.project_id,
            task_id=self.task_id,
            db_session=self.db_session,
            srt_path=self.srt_path,
            debug_mode=self.debug_mode,
            config=self.config.copy()
        )
        
        # Clones state fields
        cloned.is_initialized = self.is_initialized
        cloned.is_completed = self.is_completed
        cloned.error_message = self.error_message
        
        return cloned 