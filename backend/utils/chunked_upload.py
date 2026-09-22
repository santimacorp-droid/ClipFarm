"""
Shard upload tool
Support resumable, large-file uploading with chunked upload and merging
"""

import os
import hashlib
import shutil
import asyncio
import aiofiles
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UploadStatus(Enum):
    """Upload Status"""
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ChunkInfo:
    """Shard information"""
    chunk_number: int
    chunk_size: int
    total_chunks: int
    file_hash: str
    chunk_hash: str
    upload_id: str
    created_at: datetime
    status: UploadStatus = UploadStatus.PENDING


@dataclass
class UploadSession:
    """uploadSession"""
    upload_id: str
    filename: str
    file_size: int
    chunk_size: int
    total_chunks: int
    file_hash: str
    created_at: datetime
    status: UploadStatus = UploadStatus.PENDING
    uploaded_chunks: List[int] = None
    temp_dir: str = None
    
    def __post_init__(self):
        if self.uploaded_chunks is None:
            self.uploaded_chunks = []
        if self.temp_dir is None:
            self.temp_dir = f"/tmp/uploads/{self.upload_id}"


class ChunkedUploadManager:
    """Handler for chunked file upload"""
    
    def __init__(self, base_dir: str = "/tmp/uploads", max_file_size: int = 2 * 1024 * 1024 * 1024):
        self.base_dir = Path(base_dir)
        self.max_file_size = max_file_size
        self.active_sessions: Dict[str, UploadSession] = {}
        self.chunk_info_cache: Dict[str, List[ChunkInfo]] = {}
        
        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_upload_id(self, filename: str, file_size: int) -> str:
        """Generate upload identifier"""
        timestamp = datetime.now().isoformat()
        content = f"{filename}_{file_size}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate file hash"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _calculate_chunk_hash(self, chunk_data: bytes) -> str:
        """Calculate chunk hash value"""
        return hashlib.md5(chunk_data).hexdigest()
    
    def _validate_file_size(self, file_size: int) -> bool:
        """Validate file size"""
        return file_size <= self.max_file_size
    
    def _validate_file_type(self, filename: str) -> bool:
        """Validate file type"""
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.srt', '.vtt', '.ass', '.ssa']
        return any(filename.lower().endswith(ext) for ext in allowed_extensions)
    
    async def create_upload_session(
        self, 
        filename: str, 
        file_size: int, 
        file_hash: str,
        chunk_size: int = 2 * 1024 * 1024  # 2MB
    ) -> UploadSession:
        """Create upload session"""
        
        # Validate file size
        if not self._validate_file_size(file_size):
            raise ValueError(f"File size exceeds limit: {file_size} > {self.max_file_size}")
        
        # Validate file type
        if not self._validate_file_type(filename):
            raise ValueError(f"Unsupported file type: {filename}")
        
        # Generate upload identifier
        upload_id = self._generate_upload_id(filename, file_size)
        
        # Calculate total shards
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        
        # Create upload session
        session = UploadSession(
            upload_id=upload_id,
            filename=filename,
            file_size=file_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            file_hash=file_hash,
            created_at=datetime.now()
        )
        
        # Create temporary directory
        session.temp_dir = str(self.base_dir / upload_id)
        Path(session.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # Save Session
        self.active_sessions[upload_id] = session
        
        logger.info(f"Create upload session: {upload_id}, File: {filename}, Size: {file_size}, Total Chunks: {total_chunks}")
        
        return session
    
    async def upload_chunk(
        self, 
        upload_id: str, 
        chunk_number: int, 
        chunk_data: bytes,
        chunk_hash: str
    ) -> bool:
        """Upload shard"""
        
        # Get upload session
        session = self.active_sessions.get(upload_id)
        if not session:
            raise ValueError(f"Upload session does not exist: {upload_id}")
        
        # Validate shard number
        if chunk_number < 0 or chunk_number >= session.total_chunks:
            raise ValueError(f"Invalid shard number: {chunk_number}")
        
        # Validate shard size
        expected_size = session.chunk_size
        if chunk_number == session.total_chunks - 1:  # Last chunk of the file
            expected_size = session.file_size - (session.total_chunks - 1) * session.chunk_size
        
        if len(chunk_data) != expected_size:
            raise ValueError(f"Chunk size mismatch: expected {expected_size}, Actual {len(chunk_data)}")
        
        # Validate shard hash
        calculated_hash = self._calculate_chunk_hash(chunk_data)
        if calculated_hash != chunk_hash:
            raise ValueError(f"Chunk hash mismatch: expected {chunk_hash}, Actual {calculated_hash}")
        
        # Save shard
        chunk_path = Path(session.temp_dir) / f"chunk_{chunk_number:06d}"
        
        async with aiofiles.open(chunk_path, 'wb') as f:
            await f.write(chunk_data)
        
        # Update session status
        if chunk_number not in session.uploaded_chunks:
            session.uploaded_chunks.append(chunk_number)
        
        # Check if all chunks have been uploaded
        if len(session.uploaded_chunks) == session.total_chunks:
            session.status = UploadStatus.COMPLETED
        
        logger.info(f"Upload chunk succeeded: {upload_id}, Chunk: {chunk_number}, Progress: {len(session.uploaded_chunks)}/{session.total_chunks}")
        
        return True
    
    async def merge_chunks(self, upload_id: str, output_path: str) -> bool:
        """Merge shards"""
        
        # Get upload session
        session = self.active_sessions.get(upload_id)
        if not session:
            raise ValueError(f"Upload session does not exist: {upload_id}")
        
        # Check if all chunks have been uploaded
        if len(session.uploaded_chunks) != session.total_chunks:
            raise ValueError(f"Chunk upload incomplete: {len(session.uploaded_chunks)}/{session.total_chunks}")
        
        # Ensure output directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Merge shards
        logger.info(f"Start merging shards: {upload_id}")
        
        with open(output_path, 'wb') as output_file:
            for chunk_number in range(session.total_chunks):
                chunk_path = Path(session.temp_dir) / f"chunk_{chunk_number:06d}"
                
                if not chunk_path.exists():
                    raise FileNotFoundError(f"Chunk file does not exist: {chunk_path}")
                
                with open(chunk_path, 'rb') as chunk_file:
                    shutil.copyfileobj(chunk_file, output_file)
        
        # Verify merged file integrity
        if output_path.stat().st_size != session.file_size:
            raise ValueError(f"Final file size mismatch: expected {session.file_size}, Actual {output_path.stat().st_size}")
        
        # Validate file hash
        merged_hash = self._calculate_file_hash(str(output_path))
        if merged_hash != session.file_hash:
            raise ValueError(f"Final file hash mismatch: expected {session.file_hash}, Actual {merged_hash}")
        
        logger.info(f"Chunks successfully merged: {upload_id}, Output: {output_path}")
        
        return True
    
    async def cleanup_session(self, upload_id: str) -> bool:
        """Clean upload session"""
        
        # Get upload session
        session = self.active_sessions.get(upload_id)
        if not session:
            return False
        
        # Delete temporary directory
        temp_dir = Path(session.temp_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # Remove session from active sessions
        del self.active_sessions[upload_id]
        
        logger.info(f"Clean upload session: {upload_id}")
        
        return True
    
    def get_upload_progress(self, upload_id: str) -> Dict[str, Any]:
        """Get upload progress"""
        
        session = self.active_sessions.get(upload_id)
        if not session:
            return {"error": "Upload session does not exist"}
        
        progress = len(session.uploaded_chunks) / session.total_chunks * 100
        
        return {
            "upload_id": upload_id,
            "filename": session.filename,
            "file_size": session.file_size,
            "total_chunks": session.total_chunks,
            "uploaded_chunks": len(session.uploaded_chunks),
            "progress": round(progress, 2),
            "status": session.status.value,
            "created_at": session.created_at.isoformat()
        }
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Retrieve all active sessions"""
        
        sessions = []
        for session in self.active_sessions.values():
            progress = len(session.uploaded_chunks) / session.total_chunks * 100
            sessions.append({
                "upload_id": session.upload_id,
                "filename": session.filename,
                "file_size": session.file_size,
                "total_chunks": session.total_chunks,
                "uploaded_chunks": len(session.uploaded_chunks),
                "progress": round(progress, 2),
                "status": session.status.value,
                "created_at": session.created_at.isoformat()
            })
        
        return sessions
    
    async def cancel_upload(self, upload_id: str) -> bool:
        """Cancel Upload"""
        
        session = self.active_sessions.get(upload_id)
        if not session:
            return False
        
        # updateStatus
        session.status = UploadStatus.CANCELLED
        
        # Clean temporary files
        await self.cleanup_session(upload_id)
        
        logger.info(f"Cancel Upload: {upload_id}")
        
        return True
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up expired sessions"""
        
        from datetime import timedelta
        
        expired_sessions = []
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for upload_id, session in self.active_sessions.items():
            if session.created_at < cutoff_time:
                expired_sessions.append(upload_id)
        
        # Clean up expired sessions
        for upload_id in expired_sessions:
            asyncio.create_task(self.cleanup_session(upload_id))
        
        logger.info(f"Clean up expired sessions: {len(expired_sessions)} count")
        
        return len(expired_sessions)


# Global handler for active chunk uploads
chunked_upload_manager = ChunkedUploadManager()
