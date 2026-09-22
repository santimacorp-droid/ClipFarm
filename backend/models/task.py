"""
Task model
Define background task basic information and execution status
"""

import enum
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from .base import BaseModel, TimestampMixin

class TaskStatus(str, enum.Enum):
    """Task status enumeration"""
    PENDING = "pending"           # Pending
    RUNNING = "running"           # Running
    COMPLETED = "completed"       # Finished
    FAILED = "failed"            # Failed
    CANCELLED = "cancelled"      # Cancelled

class TaskType(str, enum.Enum):
    """Task type enumeration"""
    VIDEO_PROCESSING = "video_processing"    # Video Processing
    CLIP_GENERATION = "clip_generation"      # Slice Generation
    COLLECTION_CREATION = "collection_creation"  # Collection Creation
    EXPORT = "export"                        # Export
    CLEANUP = "cleanup"                      # Cleanup

class Task(BaseModel, TimestampMixin):
    """Task model"""
    
    __tablename__ = "tasks"
    
    # Basic Information
    name = Column(
        String(255), 
        nullable=False, 
        comment="Task Name"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="Task description"
    )
    
    # Status Information
    status = Column(
        Enum(TaskStatus), 
        default=TaskStatus.PENDING,
        nullable=False,
        comment="Task Status"
    )
    task_type = Column(
        Enum(TaskType), 
        nullable=False,
        comment="Task type"
    )
    
    # Progress information
    progress = Column(Float, default=0.0, comment="Progress percentage")
    current_step = Column(
        String(100), 
        nullable=True, 
        comment="Current Step"
    )
    total_steps = Column(
        Integer, 
        default=1,
        comment="Total Steps"
    )
    priority = Column(
        Integer, 
        default=0,
        comment="Task priority"
    )
    
    # Execution Information
    started_at = Column(
        DateTime, 
        nullable=True, 
        comment="Start Time"
    )
    completed_at = Column(
        DateTime, 
        nullable=True, 
        comment="Completion Time"
    )
    error_message = Column(
        Text, 
        nullable=True, 
        comment="Error Information"
    )
    
    # Celery task information
    celery_task_id = Column(
        String(255), 
        nullable=True, 
        comment="CeleryTaskID"
    )
    
    # Configuration Information
    task_config = Column(
        JSON, 
        nullable=True, 
        comment="Task Configuration"
    )
    result_data = Column(
        JSON, 
        nullable=True, 
        comment="Result data"
    )
    task_metadata = Column(
        JSON, 
        nullable=True, 
        comment="Task metadata"
    )
    
    # Relationship
    project_id = Column(
        String(36), 
        ForeignKey("projects.id"),
        nullable=False,
        comment="Related projectID"
    )
    project = relationship(
        "Project", 
        back_populates="tasks"
    )
    
    def __repr__(self):
        return f"<Task(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def is_running(self):
        """Is currently running"""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self):
        """Is completed successfully"""
        return self.status == TaskStatus.COMPLETED
    
    @property
    def has_error(self):
        """Has an error"""
        return self.status == TaskStatus.FAILED
    
    @property
    def duration(self):
        """Task duration (seconds))"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0
    
    def start(self):
        """Start task"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.progress = 0.0
    
    def complete(self, result_data=None):
        """Complete task"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 100.0
        if result_data:
            self.result_data = result_data
    
    def fail(self, error_message):
        """Task Failure"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
    
    def cancel(self):
        """Cancel Task"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def update_progress(self, progress, current_step=None):
        """Update progress"""
        self.progress = min(100.0, max(0.0, progress))
        if current_step:
            self.current_step = current_step
    
    def is_completed(self):
        """Check if succeeded"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    def is_running(self):
        """Check if running"""
        return self.status == TaskStatus.RUNNING
    
    def is_pending(self):
        """Check if pending"""
        return self.status == TaskStatus.PENDING
    
    def get_duration(self):
        """Get task duration"""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "status": self.status,
            "project_id": self.project_id,
            "step": self.current_step,
            "total_steps": self.total_steps,
            "progress": self.progress,
            "result": self.result_data,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": self.task_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }