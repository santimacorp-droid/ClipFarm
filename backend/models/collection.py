"""
Collection model
Defines basic information and organizational structure of a video collection
"""

import enum
from typing import Optional, List
from sqlalchemy import Column, String, Integer, ForeignKey, Enum, JSON, DateTime, Text, Table
from sqlalchemy.orm import relationship
from .base import BaseModel

class CollectionStatus(str, enum.Enum):
    """Collection status enumeration"""
    CREATED = "created"           # Created successfully
    PROCESSING = "processing"     # In progress
    COMPLETED = "completed"       # Completed
    ERROR = "error"              # Error encountered
    DELETED = "deleted"          # Deleted

# Many-to-many relationship table for slices and collections
clip_collection = Table(
    'clip_collection',
    BaseModel.metadata,
    Column('clip_id', String(36), ForeignKey('clips.id', ondelete='CASCADE'), primary_key=True),
    Column('collection_id', String(36), ForeignKey('collections.id', ondelete='CASCADE'), primary_key=True),
    Column('order_index', Integer, nullable=False, default=0, comment="Order within collection")
)

class Collection(BaseModel):
    """Collection model"""
    
    __tablename__ = "collections"
    
    # Basic information
    name = Column(
        String(255), 
        nullable=False, 
        comment="Collection name"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="Collection description"
    )
    
    # Status details
    status = Column(
        Enum(CollectionStatus), 
        default=CollectionStatus.CREATED,
        nullable=False,
        comment="Collection status"
    )
    
    # Subject details
    theme = Column(
        String(255), 
        nullable=True, 
        comment="Collection subject"
    )
    tags = Column(
        JSON, 
        nullable=True, 
        comment="Collection tags"
    )
    
    # Statistics
    total_duration = Column(
        Integer, 
        nullable=True, 
        comment="Total collection duration (seconds))"
    )
    clips_count = Column(
        Integer, 
        default=0, 
        comment="Number of slices"
    )
    
    # File details
    video_path = Column(
        String(500), 
        nullable=True, 
        comment="Collection video file path"
    )
    thumbnail_path = Column(
        String(500), 
        nullable=True, 
        comment="Collection thumbnail path"
    )
    
    # Processing details
    processing_result = Column(
        JSON, 
        nullable=True, 
        comment="Processing result data"
    )
    
    # Export details
    export_path = Column(
        String(500), 
        nullable=True, 
        comment="Collection export file path"
    )
    
    # Metadata
    collection_metadata = Column(
        JSON, 
        nullable=True, 
        comment="Collection metadata (simplified version; complete data stored in file system))"
    )
    
    # Add computed properties
    @property
    def metadata_file_path(self) -> Optional[str]:
        """Get full metadata file path"""
        if self.collection_metadata and 'metadata_file' in self.collection_metadata:
            return self.collection_metadata['metadata_file']
        return None
    
    @property
    def has_full_content(self) -> bool:
        """Whether full content file exists"""
        return self.metadata_file_path is not None
    
    @property
    def clip_ids(self) -> List[str]:
        """Get list of slice IDs"""
        if self.collection_metadata and 'clip_ids' in self.collection_metadata:
            return self.collection_metadata['clip_ids']
        return []
    
    # Foreign key association
    project_id = Column(
        String(36), 
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Project identityID"
    )
    
    # Relationships
    project = relationship(
        "Project", 
        back_populates="collections"
    )
    clips = relationship(
        "Clip", 
        secondary=clip_collection,
        back_populates="collections",
        lazy="dynamic"
    )
    
    def __repr__(self):
        return f"<Collection(id={self.id}, name='{self.name}', clips_count={self.clips_count})>"
    
    @property
    def is_processing(self):
        """True if processing is in progress"""
        return self.status == CollectionStatus.PROCESSING
    
    @property
    def is_completed(self):
        """True if processing is complete"""
        return self.status == CollectionStatus.COMPLETED
    
    @property
    def has_error(self):
        """True if error occurred"""
        return self.status == CollectionStatus.ERROR
    
    def add_clip(self, clip, order_index=None):
        """Add slice to collection"""
        if order_index is None:
            order_index = self.clips_count
        
        # Add slice using association table
        stmt = clip_collection.insert().values(
            clip_id=clip.id,
            collection_id=self.id,
            order_index=order_index
        )
        # Must be executed within a database session
        self.clips_count += 1
        return stmt
    
    def remove_clip(self, clip):
        """Remove slice from collection"""
        stmt = clip_collection.delete().where(
            clip_collection.c.clip_id == clip.id,
            clip_collection.c.collection_id == self.id
        )
        current_count = int(self.clips_count) if self.clips_count else 0
        self.clips_count = max(0, current_count - 1)
        return stmt
    
    def calculate_total_duration(self):
        """Calculate total collection duration"""
        total = 0
        for clip in self.clips:
            if clip.duration:
                total += clip.duration
        self.total_duration = total
        return total