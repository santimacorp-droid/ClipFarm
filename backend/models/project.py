"""
Project Model
Defines project metadata and status
"""

import enum
from typing import Optional
from sqlalchemy import Column, String, Text, JSON, Enum, Integer, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel

class ProjectStatus(str, enum.Enum):
    """Project status enumeration"""
    PENDING = "pending"           # Pending
    PROCESSING = "processing"     # Processing
    COMPLETED = "completed"       # Completed
    FAILED = "failed"            # Failed

class ProjectType(str, enum.Enum):
    """Project type enumeration"""
    DEFAULT = "default"           # Default
    PODCAST = "podcast"           # Podcast
    PODCAST_HIGHLIGHT = "podcast_highlight"  # Podcast Highlight
    INTERVIEW = "interview"       # Interview
    VLOG = "vlog"                 # Vlog
    STORYTELLING = "storytelling" # Storytelling
    KNOWLEDGE = "knowledge"       # Knowledge
    BUSINESS = "business"         # Business & Finance
    BUSINESS_INSIGHT = "business_insight"  # Business Insight
    TECH_TAKE = "tech_take"       # Tech & Dev
    AI_MOMENT = "ai_moment"       # AI & Future Tech
    OPINION = "opinion"          # Opinions & Commentary
    EXPERIENCE = "experience"    # Experience & How-To
    SPEECH = "speech"            # Speeches & Talks
    CONTENT_REVIEW = "content_review"  # Reviews & Breakdowns
    ENTERTAINMENT = "entertainment"    # Entertainment
    FUNNY_MOMENT = "funny_moment"      # Comedy & Fails
    HOT_TAKE = "hot_take"              # Hot Takes
    GAMING_HIGHLIGHT = "gaming_highlight"  # Gaming Highlight

class Project(BaseModel):
    """Project model"""
    
    __tablename__ = "projects"
    
    # Basic info
    name = Column(
        String(255), 
        nullable=False, 
        comment="Project name"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="Project description"
    )
    
    # Status info
    status = Column(
        Enum(ProjectStatus), 
        default=ProjectStatus.PENDING,
        nullable=False,
        comment="Project status"
    )
    
    # Project type
    project_type = Column(
        Enum(ProjectType), 
        default=ProjectType.DEFAULT,
        nullable=False,
        comment="Project category"
    )
    video_path = Column(
        String(500), 
        nullable=True, 
        comment="Video file path"
    )
    subtitle_path = Column(
        String(500), 
        nullable=True, 
        comment="Subtitle file path"
    )
    video_duration = Column(
        Integer, 
        nullable=True, 
        comment="Video duration in seconds"
    )
    thumbnail = Column(
        Text, 
        nullable=True, 
        comment="Project thumbnail (base64 encoded)"
    )
    
    # Processing configuration
    processing_config = Column(
        JSON, 
        nullable=True, 
        comment="Processing configuration parameters"
    )
    
    # Metadata
    project_metadata = Column(
        JSON, 
        nullable=True, 
        comment="Project metadata (concise, full metadata in filesystem)"
    )
    
    # Computed properties
    @property
    def storage_initialized(self) -> bool:
        """Whether storage service is initialized"""
        if self.project_metadata and 'storage_service_initialized' in self.project_metadata:
            return self.project_metadata['storage_service_initialized']
        return False
    
    @property
    def has_video_file(self) -> bool:
        """Whether video file exists"""
        return self.video_path is not None
    
    @property
    def has_subtitle_file(self) -> bool:
        """Whether subtitle file exists"""
        return self.subtitle_path is not None
    
    # Completion timestamp
    completed_at = Column(
        DateTime, 
        nullable=True, 
        comment="Project completion time"
    )
    
    # Relationships
    clips = relationship(
        "Clip", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    collections = relationship(
        "Collection", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    tasks = relationship(
        "Task", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def clips_count(self):
        """Get clip count"""
        return len(self.clips) if self.clips else 0
    
    @property
    def collections_count(self):
        """Get collection count"""
        return len(self.collections) if self.collections else 0
    
    @property
    def is_processing(self):
        """Whether project is processing"""
        return self.status == ProjectStatus.PROCESSING
    
    @property
    def is_completed(self):
        """Whether project is completed"""
        return self.status == ProjectStatus.COMPLETED
    
    @property
    def has_error(self):
        """Whether project has failed"""
        return self.status == ProjectStatus.FAILED