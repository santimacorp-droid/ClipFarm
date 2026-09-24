"""
File managementAPI
Provide file upload, download, and access functionality
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import tempfile
import uuid

from ...core.database import get_db
from ...services.storage_service import StorageService
from ...models.project import Project
from ...models.clip import Clip
from ...models.collection import Collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["File management"])

@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    project_id: str = Query(..., description="projectID"),
    db: Session = Depends(get_db)
):
    """
    Upload file (optimized storage mode)
    """
    try:
        # Validating project existence
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Initializing storage service
        storage_service = StorageService(project_id)
        
        uploaded_files = []
        
        for file in files:
            # Generating unique filename
            file_id = str(uuid.uuid4())
            file_extension = Path(file.filename).suffix if file.filename else ""
            safe_filename = f"{file_id}{file_extension}"
            
            # Determine file type
            file_type = "raw"  # Default is original file
            if file.filename:
                if file.filename.lower().endswith(('.srt', '.vtt')):
                    file_type = "subtitle"
                elif file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    file_type = "video"
            
            # Saving file to filesystem
            file_path = Path(tempfile.gettempdir()) / safe_filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Use storage service to save file
            saved_path = storage_service.save_file(file_path, safe_filename, file_type)
            
            # Updating project database record
            if file_type == "video":
                project.video_path = saved_path
            elif file_type == "subtitle":
                project.subtitle_path = saved_path
            
            # Clean up temporary files
            file_path.unlink()
            
            uploaded_files.append({
                "original_name": file.filename,
                "saved_path": saved_path,
                "file_type": file_type,
                "file_size": file.size
            })
        
        # Committing database changes
        db.commit()
        
        logger.info(f"project {project_id} Uploaded {len(uploaded_files)} Files")
        
        return {
            "success": True,
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "message": f"Successful upload {len(uploaded_files)} Files"
        }
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@router.get("/clips/{clip_id}/content")
async def get_clip_content(
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    Get complete slice content
    """
    try:
        # Get slice record
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="Slice does not exist")
        
        # From filesystem retrieve full content
        from ...repositories.clip_repository import ClipRepository
        clip_repo = ClipRepository(db)
        content = clip_repo.get_clip_content(clip_id)
        
        if not content:
            raise HTTPException(status_code=404, detail="Slice content does not exist")
        
        return {
            "clip_id": clip_id,
            "content": content,
            "metadata": {
                "title": clip.title,
                "duration": clip.duration,
                "score": clip.score,
                "video_path": clip.video_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Getting slice content failed: {e}")
        raise HTTPException(status_code=500, detail=f"Getting slice content failed: {str(e)}")

@router.get("/collections/{collection_id}/content")
async def get_collection_content(
    collection_id: str,
    db: Session = Depends(get_db)
):
    """
    Get complete ensemble content
    """
    try:
        # Get set record
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail="Set does not exist")
        
        # From filesystem retrieve full content
        from ...repositories.collection_repository import CollectionRepository
        collection_repo = CollectionRepository(db)
        content = collection_repo.get_collection_content(collection_id)
        
        if not content:
            raise HTTPException(status_code=404, detail="Bundle content does not exist")
        
        return {
            "collection_id": collection_id,
            "content": content,
            "metadata": {
                "name": collection.name,
                "description": collection.description,
                "clips_count": collection.clips_count,
                "export_path": collection.export_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Getting bundle content failed: {e}")
        raise HTTPException(status_code=500, detail=f"Getting bundle content failed: {str(e)}")

@router.api_route("/clips/{clip_id}/download", methods=["GET", "HEAD"])
async def download_clip_file(
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    Download slice file
    """
    try:
        import urllib.parse
        from ...core.path_utils import find_clip_video_file
        from ...utils.video_processor import VideoProcessor

        file_path, clip = find_clip_video_file(None, clip_id, db=db)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="Slice file does not exist")

        clip_title = (clip.title if clip else None) or getattr(clip, 'generated_title', None) or file_path.stem or f"clip_{clip_id}"
        safe_name = VideoProcessor.sanitize_filename(clip_title)
        filename = f"{safe_name}.mp4"
        encoded_filename = urllib.parse.quote(filename.encode('utf-8'))

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Downloading slice file failed: {e}")
        raise HTTPException(status_code=500, detail=f"Downloading slice file failed: {str(e)}")

def _serve_video_file(file_path: Path, request: Optional[Request] = None, format: Optional[str] = None):
    import subprocess
    import os

    user_agent = request.headers.get("user-agent", "") if request else ""
    wants_webm = (format == "webm") or ("QtWebEngine" in user_agent)

    media_type = "video/mp4"
    serve_path = str(file_path)

    if wants_webm:
        webm_path = file_path.with_suffix(".preview.webm")
        if not webm_path.exists() or webm_path.stat().st_size == 0:
            try:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(file_path),
                    "-vf", "scale=-2:720",
                    "-c:v", "libvpx-vp9",
                    "-b:v", "0",
                    "-crf", "38",
                    "-deadline", "realtime",
                    "-cpu-used", "8",
                    "-c:a", "libopus",
                    "-f", "webm",
                    str(webm_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False)
            except Exception as conv_err:
                logger.warning(f"On-demand WebM preview transcode failed: {conv_err}")

        if webm_path.exists() and webm_path.stat().st_size > 0:
            serve_path = str(webm_path)
            media_type = "video/webm"

    return FileResponse(
        path=str(serve_path),
        media_type=media_type,
        filename=os.path.basename(serve_path),
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.api_route("/projects/{project_id}/clips/{clip_id}", methods=["GET", "HEAD"])
async def get_project_clip_video(
    project_id: str,
    clip_id: str,
    request: Request,
    format: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get project slice video (frontend compatible playback)
    """
    try:
        from ...core.path_utils import find_clip_video_file

        file_path, clip = find_clip_video_file(project_id, clip_id, db=db)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="Slice file does not exist")

        # Verify whether slice belongs to this project if clip is bound to a different project
        if clip and clip.project_id and str(clip.project_id) != str(project_id):
            raise HTTPException(status_code=403, detail="Slice does not belong to project")
        
        return _serve_video_file(file_path, request=request, format=format)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Getting project slice video failed: {e}")
        raise HTTPException(status_code=500, detail=f"Getting project slice video failed: {str(e)}")

@router.api_route("/collections/{collection_id}/download", methods=["GET", "HEAD"])
async def download_collection_file(
    collection_id: str,
    db: Session = Depends(get_db)
):
    """
    Download ensemble file
    """
    try:
        import urllib.parse
        from ...core.path_utils import find_collection_video_file
        from ...utils.video_processor import VideoProcessor

        file_path, collection = find_collection_video_file(None, collection_id, db=db)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="Bundle file does not exist")

        col_name = (collection.name if collection else None) or file_path.stem or f"collection_{collection_id}"
        safe_name = VideoProcessor.sanitize_filename(col_name)
        filename = f"{safe_name}.mp4"
        encoded_filename = urllib.parse.quote(filename.encode('utf-8'))

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Downloading bundle file failed: {e}")
        raise HTTPException(status_code=500, detail=f"Downloading bundle file failed: {str(e)}")

@router.api_route("/projects/{project_id}/collections/{collection_id}", methods=["GET", "HEAD"])
async def get_project_collection_video(
    project_id: str,
    collection_id: str,
    request: Request,
    format: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get project ensemble video (frontend compatible playback) ID and set ID
    """
    try:
        from ...core.path_utils import find_collection_video_file

        file_path, collection = find_collection_video_file(project_id, collection_id, db=db)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="Bundle file does not exist")

        return _serve_video_file(file_path, request=request, format=format)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Getting project bundle video failed: {e}")
        raise HTTPException(status_code=500, detail=f"Getting project bundle video failed: {str(e)}")

@router.get("/projects/{project_id}/storage-info")
async def get_project_storage_info(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Get project storage information
    """
    try:
        # Validating project existence
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Get storage information
        storage_service = StorageService(project_id)
        storage_info = storage_service.get_project_storage_info()
        
        return {
            "project_id": project_id,
            "storage_info": storage_info,
            "file_paths": {
                "video_path": project.video_path,
                "subtitle_path": project.subtitle_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Getting project storage information failed: {e}")
        raise HTTPException(status_code=500, detail=f"Getting project storage information failed: {str(e)}")

@router.delete("/projects/{project_id}/cleanup")
async def cleanup_project_files(
    project_id: str,
    keep_days: int = Query(30, description="Retention days"),
    db: Session = Depends(get_db)
):
    """
    Clean up old project files
    """
    try:
        # Validating project existence
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Clean up old files
        storage_service = StorageService(project_id)
        storage_service.cleanup_old_files(project_id, keep_days)
        
        return {
            "success": True,
            "project_id": project_id,
            "keep_days": keep_days,
            "message": f"project {project_id} Old file cleanup complete"
        }
        
    except Exception as e:
        logger.error(f"Cleaning up project files failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cleaning up project files failed: {str(e)}")
