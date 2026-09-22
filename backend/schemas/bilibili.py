"""
BBilibili-relatedSchema
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Union
from uuid import UUID
from datetime import datetime


class BilibiliAccountCreate(BaseModel):
    """Creating Bilibili account"""
    username: str = Field(default="qr_login", description="Username")
    password: str = Field(default="", description="Password")
    nickname: Optional[str] = Field(None, description="Nickname")
    cookie_content: str = Field(..., description="cookieFile content")


class BilibiliAccountResponse(BaseModel):
    """BAccount response"""
    id: Union[int, str]  # Supports Integer andUUID
    username: str
    nickname: Optional[str]
    status: str
    is_default: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class QRLoginRequest(BaseModel):
    """QR code login request"""
    nickname: Optional[str] = Field(None, description="Nickname")


class QRLoginResponse(BaseModel):
    """QR code login response"""
    session_id: str
    status: str
    message: str


class UploadRequest(BaseModel):
    """Submission request"""
    clip_ids: List[str] = Field(..., description="Slice IDs to be submitted")
    account_id: Union[int, str] = Field(..., description="Used accountID")
    title: str = Field(..., description="Title")
    description: str = Field(..., description="Description")
    tags: List[str] = Field(default=[], description="Tag list")
    partition_id: int = Field(..., description="CategoryID")
    sub_partition_id: Optional[int] = Field(None, description="Sub-partition ID (optional))")


class UploadRecordResponse(BaseModel):
    """Submission record response"""
    id: Union[int, str]
    task_id: Optional[str]
    project_id: Optional[UUID]
    account_id: Union[int, str]
    clip_id: str
    title: str
    description: Optional[str]
    tags: Optional[str]
    partition_id: int
    video_path: Optional[str]
    bv_id: Optional[str]
    av_id: Optional[str]
    status: str
    error_message: Optional[str]
    progress: int
    file_size: Optional[int]
    upload_duration: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    # Associated information
    account_username: Optional[str] = None
    account_nickname: Optional[str] = None
    project_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class UploadStatusResponse(BaseModel):
    """Submission status response"""
    id: UUID
    status: str
    bvid: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
