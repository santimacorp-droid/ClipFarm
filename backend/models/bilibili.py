"""
BSite-related database model.
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .base import Base


class BilibiliAccount(Base):
    """BSite account table."""
    __tablename__ = "bilibili_accounts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    nickname = Column(String(100))
    cookies = Column(Text)  # Encrypted storage of.cookies
    status = Column(String(20), default="active")  # active/inactive/banned
    is_default = Column(Boolean, default=False)
    
    # Account information.
    uid = Column(String(50))  # BSite user.ID
    level = Column(Integer, default=0)  # User level.
    is_vip = Column(Boolean, default=False)  # isVIP
    can_upload = Column(Boolean, default=True)  # Whether a submission is allowed.
    
    # Use statistics.
    last_used_at = Column(DateTime)  # Last used time.
    upload_count = Column(Integer, default=0)  # Number of uploads.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # relation
    upload_records = relationship("BilibiliUploadRecord", back_populates="account")


class BilibiliUploadRecord(Base):
    """BTable of upload records for site submissions."""
    __tablename__ = "bilibili_upload_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), unique=True, index=True)  # Task queue.ID
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("bilibili_accounts.id"), nullable=False)
    clip_id = Column(String(255))  # sliceID
    
    # Submission content.
    title = Column(String(200), nullable=False)
    description = Column(Text)
    tags = Column(Text)  # JSONString storage.
    partition_id = Column(Integer, default=17)  # Partition ID; default for single-player games.
    video_path = Column(String(500))  # Video file path.
    
    # Submission result.
    bv_id = Column(String(20))  # The BVID after successful submission.
    av_id = Column(String(20))  # AV ID
    status = Column(String(20), default="pending")  # pending/processing/completed/failed
    error_message = Column(Text)  # Error message.
    
    # Upload progress and statistics.
    progress = Column(Integer, default=0)  # Upload progress. 0-100
    file_size = Column(Integer)  # File size (in bytes).)
    upload_duration = Column(Integer)  # Time spent uploading (seconds).)
    
    # Timestamp.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # relation
    account = relationship("BilibiliAccount", back_populates="upload_records")

# For backward compatibility, keep the old class name.
UploadRecord = BilibiliUploadRecord

