"""
Base model definition
Contains all base classes and mixins
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, MetaData
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID

# Create MetaData instance; ensure table is not redefined
metadata = MetaData()

# Create base class
Base = declarative_base(metadata=metadata)

def get_utc_now():
    """Gets the current UTC time"""
    return datetime.now(timezone.utc)

class TimestampMixin:
    """Timestamp mixin class; adds creation and update time to models"""
    
    created_at = Column(
        DateTime(timezone=True), 
        default=get_utc_now, 
        nullable=False,
        comment="Creation time"
    )
    updated_at = Column(
        DateTime(timezone=True), 
        default=get_utc_now, 
        onupdate=get_utc_now, 
        nullable=False,
        comment="Update time"
    )

def generate_uuid():
    """Generates a UUID string"""
    return str(uuid.uuid4())

class BaseModel(Base, TimestampMixin):
    """Base model class; contains common fields"""
    
    __abstract__ = True
    
    id = Column(
        String(36), 
        primary_key=True, 
        default=generate_uuid,
        index=True,
        comment="Primary keyID"
    )
    
    def __repr__(self):
        """String representation of the model"""
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self):
        """Converts to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: dict):
        """Updates the model from a dictionary"""
        for key, value in data.items():
            if hasattr(self, key) and key != 'id':
                setattr(self, key, value)
        return self 