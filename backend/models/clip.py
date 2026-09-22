"""
Slice model
Defines basic information and status of a video slice
"""

import enum
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from .base import BaseModel

class ClipStatus(str, enum.Enum):
    """Slice state enumeration"""
    PENDING = "pending"           # To be processed
    PROCESSING = "processing"     # In progress
    COMPLETED = "completed"       # Completed
    FAILED = "failed"            # Failed

class Clip(BaseModel):
    """Slice model"""
    
    __tablename__ = "clips"
    
    # Basic information
    title = Column(
        String(255), 
        nullable=False, 
        comment="Slice title"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="Slice description"
    )
    
    # Status information
    status = Column(
        Enum(ClipStatus), 
        default=ClipStatus.PENDING,
        nullable=False,
        comment="Slice status"
    )
    
    # Time information
    start_time = Column(
        Integer, 
        nullable=False, 
        comment="Start time (seconds))"
    )
    end_time = Column(
        Integer, 
        nullable=False, 
        comment="End time (seconds))"
    )
    duration = Column(
        Integer, 
        nullable=False, 
        comment="Slice duration (seconds))"
    )
    
    # Rating information
    score = Column(
        Float, 
        nullable=True, 
        comment="Slice rating"
    )
    recommendation_reason = Column(
        Text, 
        nullable=True, 
        comment="Recommendation reason"
    )
    
    # File information
    video_path = Column(
        String(500), 
        nullable=True, 
        comment="Path to slice video file"
    )
    thumbnail_path = Column(
        String(500), 
        nullable=True, 
        comment="Path to thumbnail image file"
    )
    
    # Processing information
    processing_step = Column(
        Integer, 
        nullable=True, 
        comment="Processing steps(1-6)"
    )
    
    # Labels and metadata
    tags = Column(
        JSON, 
        nullable=True, 
        comment="Slice label"
    )
    clip_metadata = Column(
        JSON, 
        nullable=True, 
        comment="Slice metadata (compact version; complete data stored in filesystem))"
    )
    
    # Add computed properties
    @property
    def metadata_file_path(self) -> Optional[str]:
        """Get path to complete metadata file"""
        if self.clip_metadata and 'metadata_file' in self.clip_metadata:
            return self.clip_metadata['metadata_file']
        return None
    
    @property
    def has_full_content(self) -> bool:
        """Whether a complete content file exists"""
        return self.metadata_file_path is not None
    
    # Foreign key association
    project_id = Column(
        String(36), 
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Belongs to projectID"
    )
    
    # Relationship
    project = relationship(
        "Project", 
        back_populates="clips"
    )
    collections = relationship(
        "Collection", 
        secondary="clip_collection",
        back_populates="clips"
    )
    
    def __repr__(self):
        return f"<Clip(id={self.id}, title='{self.title}', duration={self.duration}s)>"
    
    @property
    def platform_advisory(self):
        """Returns the platform duration advisory dict for this clip."""
        if self.clip_metadata and isinstance(self.clip_metadata, dict) and "platform_advisory" in self.clip_metadata:
            return self.clip_metadata["platform_advisory"]
        from ..core.platform_advisor import get_platform_advisory
        return get_platform_advisory(float(self.duration or 0.0))

    @property
    def social_copy(self):
        """Returns the generated social post caption & hashtags dict for this clip."""
        if self.clip_metadata and isinstance(self.clip_metadata, dict) and "social_copy" in self.clip_metadata:
            return self.clip_metadata["social_copy"]
        return None

    @property
    def is_processing(self):
        """Is currently processing"""
        return self.status == ClipStatus.PROCESSING
    
    @property
    def is_completed(self):
        """Has finished"""
        return self.status == ClipStatus.COMPLETED
    
    @property
    def has_error(self):
        """Has error"""
        return self.status == ClipStatus.FAILED
    
    def get_time_range(self) -> str:
        """Get time range string"""
        try:
            start_time = int(self.start_time) if self.start_time else 0
            end_time = int(self.end_time) if self.end_time else 0
            start_min, start_sec = divmod(start_time, 60)
            end_min, end_sec = divmod(end_time, 60)
            return f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
        except (TypeError, ValueError):
            return "00:00 - 00:00"
    
    def calculate_duration(self):
        """Compute slice duration"""
        self.duration = self.end_time - self.start_time
        return self.duration