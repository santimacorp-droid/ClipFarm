"""
projectAPIrouting
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.services.project_service import ProjectService
from backend.services.processing_service import ProcessingService
from backend.services.websocket_notification_service import WebSocketNotificationService
# Lazy import to avoid triggering too earlycelery_appimport chain
# from backend.tasks.processing import process_video_pipeline
from backend.core.websocket_manager import manager as websocket_manager
from backend.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter,
    ProjectType, ProjectStatus
)
from backend.schemas.base import PaginationParams
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    """Dependency to get project service."""
    return ProjectService(db)


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingService:
    """Dependency to get processing service."""
    return ProcessingService(db)


def get_websocket_service():
    """Dependency to get websocket notification service."""
    return WebSocketNotificationService


@router.post("/upload", response_model=ProjectResponse)
async def upload_files(
    video_file: UploadFile = File(...),
    srt_file: Optional[UploadFile] = File(None),
    project_name: str = Form(...),
    video_category: Optional[str] = Form(None),
    caption_style: Optional[str] = Form("hormozi_yellow"),
    duration_mode: Optional[str] = Form("tiktok_crp"),
    aspect_ratio: Optional[str] = Form("9:16_blur"),
    show_hook_banner: Optional[bool] = Form(True),
    watermark_preset_id: Optional[str] = Form("none"),
    watermark_text: Optional[str] = Form(None),
    watermark_text_opacity: Optional[float] = Form(0.50),
    watermark_text_position: Optional[str] = Form("lower_center"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Upload video file and optional subtitle file to create a new project. If no subtitle is provided, Whisper will automatically generate one."""
    try:
        # Validate video file type
        if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid video file format")
        
        # Validate subtitle file type (if provided))
        if srt_file and not srt_file.filename.lower().endswith('.srt'):
            raise HTTPException(status_code=400, detail="Invalid subtitle file format")
        
        # Create project data
        subtitle_info = srt_file.filename if srt_file else "Whisper auto-generated"
        project_data = ProjectCreate(
            name=project_name,
            description=f"Video: {video_file.filename}, Subtitle: {subtitle_info}",
            project_type=ProjectType.KNOWLEDGE,  # Default type
            status=ProjectStatus.PENDING,
            source_url=None,
            source_file=video_file.filename,
            settings={
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "srt_file": subtitle_info,
                "caption_style": caption_style or "hormozi_yellow",
                "duration_mode": duration_mode or "tiktok_crp",
                "aspect_ratio": aspect_ratio or "9:16_blur",
                "show_hook_banner": True if show_hook_banner is None else show_hook_banner,
                "watermark_preset_id": watermark_preset_id or "none",
                "watermark_text": watermark_text,
                "watermark_text_opacity": watermark_text_opacity,
                "watermark_text_position": watermark_text_position or "lower_center"
            }
        )
        
        # Create project
        project = project_service.create_project(project_data)
        
        # Save file to project directory
        project_id = str(project.id)
        from ...core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        
        # Save video file in chunks to prevent high memory usage
        video_path = raw_dir / "input.mp4"
        with open(video_path, "wb") as f:
            while chunk := await video_file.read(8 * 1024 * 1024):
                f.write(chunk)
        
        # Update video path for project
        project.video_path = str(video_path)
        project_service.db.commit()
        
        # Generate thumbnail immediately (synchronous processing))
        try:
            from ...utils.thumbnail_generator import generate_project_thumbnail
            logger.info(f"Starting for project {project_id} Generating thumbnail...")
            thumbnail_data = generate_project_thumbnail(project_id, video_path)
            if thumbnail_data:
                project.thumbnail = thumbnail_data
                project_service.db.commit()
                logger.info(f"project {project_id} Thumbnail generated and saved successfully")
            else:
                logger.warning(f"project {project_id} Thumbnail generation failed")
        except Exception as e:
            logger.error(f"Error generating project thumbnail: {e}")
            # Thumbnail generation failure does not impact main flow; will retry in background task
        
        # Processing subtitle file (if provided))
        srt_path = None
        if srt_file:
            # Subtitle file provided
            srt_path = raw_dir / "input.srt"
            with open(srt_path, "wb") as f:
                while chunk := await srt_file.read(1024 * 1024):
                    f.write(chunk)
            logger.info(f"User-provided subtitle file saved: {srt_path}")
        
        # Launch async processing task
        try:
            from ...tasks.import_processing import process_import_task
            
            # Check if identical project is already being processed
            from ...models.task import Task, TaskStatus
            from sqlalchemy import or_
            existing_task = project_service.db.query(Task).filter(
                Task.project_id == project_id,
                Task.status == TaskStatus.RUNNING,
                or_(Task.name.ilike('%import%'), Task.name.like('%import%'))
            ).first()
            
            if existing_task:
                logger.warning(f"project {project_id} Processing task already running; skip duplicate start")
            else:
                # Submit asynchronous task
                celery_task = process_import_task.delay(
                    project_id=project_id,
                    video_path=str(video_path),
                    srt_file_path=str(srt_path) if srt_path else None
                )
                
                logger.info(f"project {project_id} Asynchronous processing task started, CelerytaskID: {celery_task.id}")
            
        except Exception as e:
            logger.error(f"Launch project {project_id} Asynchronous processing failed: {str(e)}")
            # Even if async task startup fails, return successful project creation
            # Users can restart processing via the retry button
        
        # Returning project response
        response_data = {
            "id": str(project.id),
            "name": str(project.name),
            "description": str(project.description) if project.description else None,
            "project_type": ProjectType(project.project_type.value),
            "status": ProjectStatus(project.status.value),
            "source_url": project.project_metadata.get("source_url") if project.project_metadata else None,
            "source_file": str(project.video_path) if project.video_path else None,
            "video_path": str(video_path),  # addvideo_pathfield
            "settings": {
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "srt_file": subtitle_info
            },  # Contains only serializable data
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "completed_at": project.completed_at,
            "total_clips": 0,
            "total_collections": 0,
            "total_tasks": 0
        }
        
        # Thumbnail will be generated in asynchronous task
        response_data["thumbnail"] = None
        
        return ProjectResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create project while uploading file")
        raise HTTPException(status_code=500, detail="Project creation failed. Please try again later")


class LocalImportRequest(BaseModel):
    file_path: str
    project_name: Optional[str] = None
    video_category: Optional[str] = "podcast"
    caption_style: Optional[str] = "hormozi_yellow"
    duration_mode: Optional[str] = "tiktok_crp"
    aspect_ratio: Optional[str] = "9:16_blur"
    show_hook_banner: Optional[bool] = True
    watermark_preset_id: Optional[str] = "none"
    watermark_text: Optional[str] = None
    watermark_text_opacity: Optional[float] = 0.50
    watermark_text_position: Optional[str] = "lower_center"
    srt_path: Optional[str] = None


@router.post("/import-local", response_model=ProjectResponse)
async def import_local_file(
    data: LocalImportRequest,
    project_service: ProjectService = Depends(get_project_service)
):
    """Create project directly from an existing file path on the local filesystem (Native Desktop Mode)."""
    src_file = Path(data.file_path).resolve()
    if not src_file.is_file():
        raise HTTPException(status_code=400, detail=f"Local video file not found: {data.file_path}")

    if not src_file.name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid video file format")

    proj_name = data.project_name.strip() if (data.project_name and data.project_name.strip()) else src_file.stem
    subtitle_info = Path(data.srt_path).name if data.srt_path else "Whisper auto-generated"

    project_data = ProjectCreate(
        name=proj_name,
        description=f"Local: {src_file.name}, Subtitle: {subtitle_info}",
        project_type=ProjectType.KNOWLEDGE,
        status=ProjectStatus.PENDING,
        source_url=None,
        source_file=str(src_file),
        settings={
            "video_category": data.video_category or "podcast",
            "video_file": src_file.name,
            "srt_file": subtitle_info,
            "caption_style": data.caption_style or "hormozi_yellow",
            "duration_mode": data.duration_mode or "tiktok_crp",
            "aspect_ratio": data.aspect_ratio or "9:16_blur",
            "show_hook_banner": True if data.show_hook_banner is None else data.show_hook_banner,
            "watermark_preset_id": data.watermark_preset_id or "none",
            "watermark_text": data.watermark_text,
            "watermark_text_opacity": data.watermark_text_opacity,
            "watermark_text_position": data.watermark_text_position or "lower_center"
        }
    )

    project = project_service.create_project(project_data)
    project_id = str(project.id)

    from ...core.path_utils import get_project_raw_directory
    raw_dir = get_project_raw_directory(project_id)
    target_video = raw_dir / "input.mp4"

    try:
        if target_video.exists():
            target_video.unlink()
        try:
            target_video.symlink_to(src_file)
        except (OSError, NotImplementedError):
            import shutil
            shutil.copy2(src_file, target_video)
    except Exception as e:
        logger.warning(f"Could not symlink local file, falling back to copy: {e}")
        import shutil
        shutil.copy2(src_file, target_video)

    project.video_path = str(target_video)
    project_service.db.commit()

    # Generate thumbnail immediately
    try:
        from ...utils.thumbnail_generator import generate_project_thumbnail
        thumbnail_data = generate_project_thumbnail(project_id, target_video)
        if thumbnail_data:
            project.thumbnail = thumbnail_data
            project_service.db.commit()
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")

    target_srt = None
    if data.srt_path and Path(data.srt_path).is_file():
        target_srt = raw_dir / "input.srt"
        try:
            if target_srt.exists():
                target_srt.unlink()
            target_srt.symlink_to(Path(data.srt_path).resolve())
        except Exception:
            import shutil
            shutil.copy2(Path(data.srt_path).resolve(), target_srt)

    # Launch processing pipeline
    try:
        from ...tasks.import_processing import process_import_task
        process_import_task.apply_async(
            args=[project_id, str(target_video), str(target_srt) if target_srt else None]
        )
    except Exception as e:
        logger.error(f"Failed to launch import task: {e}")

    res = project_service.get_project_with_stats(project_id)
    if not res:
        raise HTTPException(status_code=500, detail="Failed to retrieve newly created project")
    return res


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service)
):
    """Create a new project."""
    try:
        project = project_service.create_project(project_data)
        # Convert to response (simplified for now)
        return ProjectResponse(
            id=str(project.id),  # Use actual project ID
            name=str(project.name),
            description=str(project.description) if project.description else None,
            project_type=ProjectType(project.project_type.value),
            status=ProjectStatus(project.status.value),
            source_url=project.project_metadata.get("source_url") if project.project_metadata else None,
            source_file=str(project.video_path) if project.video_path else None,
            settings=project.processing_config or {},
            created_at=project.created_at,
            updated_at=project.updated_at,
            completed_at=project.completed_at,
            total_clips=0,
            total_collections=0,
            total_tasks=0
        )
    except Exception as e:
        logger.exception("Project creation failed")
        raise HTTPException(status_code=500, detail="Project creation failed. Please try again later")


@router.get("/", response_model=ProjectListResponse)
async def get_projects(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=500, description="Page size"),
    status: Optional[str] = Query(None, description="Filter by status"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get paginated projects with optional filtering."""
    try:
        pagination = PaginationParams(page=page, size=size)
        
        filters = None
        if status or project_type or search:
            # Converting string to enum value
            status_enum = None
            if status:
                try:
                    status_enum = ProjectStatus(status)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
            
            project_type_enum = None
            if project_type:
                try:
                    project_type_enum = ProjectType(project_type)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid project_type: {project_type}")
            
            filters = ProjectFilter(
                status=status_enum,
                project_type=project_type_enum,
                search=search
            )
        
        return project_service.get_projects_paginated(pagination, filters)
    except Exception as e:
        logger.exception("Failed to get project list")
        raise HTTPException(status_code=500, detail="Failed to retrieve project list, please try again later")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    include_clips: bool = Query(False, description="Whether to include slice data"),
    include_collections: bool = Query(False, description="Whether to include collection data"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a project by ID."""
    try:
        project = project_service.get_project_with_stats(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # If including is requiredclipsAndcollectionsIf data, load them
        clips_data = None
        collections_data = None
        
        if include_clips or include_collections:
            from ...services.clip_service import ClipService
            from ...services.collection_service import CollectionService
            from ...core.database import get_db
            
            # Get database session
            db = next(get_db())
            
            if include_clips:
                clip_service = ClipService(db)
                clips = clip_service.get_multi(filters={"project_id": project_id})
                # Converted to dictionary format
                clips_data = [clip.to_dict() if hasattr(clip, 'to_dict') else clip.__dict__ for clip in clips]
            
            if include_collections:
                collection_service = CollectionService(db)
                collections = collection_service.get_multi(filters={"project_id": project_id})
                # Converted to dictionary format
                collections_data = [collection.to_dict() if hasattr(collection, 'to_dict') else collection.__dict__ for collection in collections]
        
        # Create containingclipsAndcollectionsResponse data of
        response_data = project.model_dump() if hasattr(project, 'model_dump') else project.__dict__
        if clips_data is not None:
            response_data['clips'] = clips_data
        if collections_data is not None:
            response_data['collections'] = collections_data
        
        # Return updated response
        return ProjectResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get project details: %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to get project details; please try again later")


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    project_service: ProjectService = Depends(get_project_service)
):
    """Update a project."""
    try:
        project = project_service.update_project(project_id, project_data)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Convert to response (simplified)
        return ProjectResponse(
            id=str(project_id),  # Keep as string for UUID
            name=project_data.name or "Updated Project",
            description=project_data.description,
            project_type=ProjectType.DEFAULT,  # Use enum
            status=ProjectStatus.PENDING,  # Use enum
            source_url=None,
            source_file=None,
            settings=project_data.settings or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            completed_at=None,
            total_clips=0,
            total_collections=0,
            total_tasks=0
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Update project failed: %s", project_id)
        raise HTTPException(status_code=500, detail="Project update failed. Please try again later")


class BatchDeleteProjectsRequest(BaseModel):
    project_ids: List[str]


@router.post("/batch-delete")
async def batch_delete_projects(
    req: BatchDeleteProjectsRequest,
    project_service: ProjectService = Depends(get_project_service)
):
    """Batch delete multiple projects and all their associated files."""
    deleted = []
    failed = []
    for pid in req.project_ids:
        try:
            if project_service.delete_project_with_files(pid):
                deleted.append(pid)
            else:
                failed.append(pid)
        except Exception as e:
            logger.warning("Failed to delete project %s in batch: %s", pid, e)
            failed.append(pid)
    return {
        "message": f"Successfully deleted {len(deleted)} projects",
        "deleted": deleted,
        "failed": failed,
        "count": len(deleted)
    }


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete a project and all its related files."""
    try:
        success = project_service.delete_project_with_files(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project and all related files deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete project: %s", project_id)
        raise HTTPException(status_code=500, detail="Project deletion failed. Please try again later")


@router.post("/sync-all-data")
async def sync_all_projects_data(
    db: Session = Depends(get_db)
):
    """Synchronizing all projects' data to database"""
    try:
        from ...services.data_sync_service import DataSyncService
        from ...core.config import get_data_directory
        
        data_dir = get_data_directory()
        sync_service = DataSyncService(db)
        
        result = sync_service.sync_all_projects_from_filesystem(data_dir)
        
        return {
            "message": "Data synchronization complete",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data synchronization failed: {str(e)}")


@router.post("/{project_id}/sync-data")
async def sync_project_data(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Synchronize specified project's data to database"""
    try:
        from ...services.data_sync_service import DataSyncService
        from ...core.path_utils import get_project_directory
        
        project_dir = get_project_directory(project_id)
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="Project directory does not exist")
        
        sync_service = DataSyncService(db)
        result = sync_service.sync_project_from_filesystem(project_id, project_dir)
        
        if result.get("success"):
            return {
                "message": "Project data synchronized successfully",
                "result": result
            }
        else:
            raise HTTPException(status_code=500, detail=f"Data synchronization failed: {result.get('error')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data synchronization failed: {str(e)}")


@router.post("/{project_id}/process")
async def start_processing(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Start processing a project using Celery task queue."""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check project status
        if project.status.value not in ["pending", "failed"]:
            raise HTTPException(status_code=400, detail="Project is not in pending or failed status")
        
        # Getting video andSRTFile path
        video_path = project.video_path
        srt_path = None
        
        # Fromprocessing_configRetrieve fromSRTFile path
        if project.processing_config and "subtitle_path" in project.processing_config:
            srt_path = project.processing_config["subtitle_path"]
        
        # Validate video file exists
        if not video_path or not Path(video_path).exists():
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
        
        # Validate and resolve SRT file path
        from backend.utils.subtitle_validator import validate_subtitle_file
        candidate_srt = None
        if srt_path:
            candidate_srt = Path(srt_path)
        else:
            video_dir = Path(video_path).parent
            candidate_srt = video_dir / "input.srt"
            if not candidate_srt.exists():
                meta_srt = video_dir.parent / "metadata" / "input.srt"
                if meta_srt.exists():
                    candidate_srt = meta_srt

        if candidate_srt and candidate_srt.exists() and validate_subtitle_file(candidate_srt, video_path=video_path):
            srt_path = str(candidate_srt)
        else:
            if candidate_srt and candidate_srt.exists():
                logger.warning(f"Ignoring invalid/placeholder subtitle file: {candidate_srt}")
            srt_path = None
        
        # Update project status to processing
        project_service.update_project_status(project_id, "processing")
        
        # sendWebSocketNotification: Processing started
        await websocket_service.send_processing_started(
            project_id=project_id,
            message="Start video processing workflow"
        )
        
        # Lazy import to avoid triggering too earlycelery_appimport chain
        from backend.tasks.processing import process_video_pipeline
        
        # SubmitCelerytask
        celery_task = process_video_pipeline.delay(
            project_id=project_id,
            input_video_path=str(video_path),
            input_srt_path=str(srt_path) if srt_path else None
        )
        
        # Create processing task record
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type="VIDEO_PROCESSING"
        )
        
        return {
            "message": "Processing started successfully",
            "project_id": project_id,
            "task_id": task_result.id,
            "celery_task_id": celery_task.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Sending error notification
        try:
            await websocket_service.send_processing_error(
                project_id=int(project_id),
                error=str(e),
                step="initialization"
            )
        except:
            pass
        logger.exception("Failed to start project processing: %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to start processing, please try again later")


@router.post("/{project_id}/retry")
async def retry_processing(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Retry processing a project from the beginning."""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check project status - allow failed, completed, in progress and waiting states to retry
        if project.status.value not in ["failed", "completed", "processing", "pending"]:
            raise HTTPException(status_code=400, detail="Project is not in failed, completed, processing, or pending status")
        
        # Resetting project state
        project_service.update_project_status(project_id, "pending")
        
        # sendWebSocketNotification - DisabledWebSocketNotify
        # await websocket_service.send_processing_started(
        #     project_id=int(project_id),
        #     message="Restart processing workflow"
        # )
        
        # Retrieve file path and resubmit task
        from ...core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        video_path = raw_dir / "input.mp4"  # Use standard input.mp4 file name
        srt_path = raw_dir / "input.srt"    # Use standard input.srt file name
        if not srt_path.exists():
            meta_srt = raw_dir.parent / "metadata" / "input.srt"
            if meta_srt.exists():
                srt_path = meta_srt
        
        # Check if video file exists, attempt re-download if not found
        if not video_path.exists():
            logger.warning(f"Video file not found: {video_path}, Attempting redownload")
            
            # Check for source in project metadataURL
            if hasattr(project, 'project_metadata') and project.project_metadata:
                source_url = project.project_metadata.get('source_url')
                if source_url:
                    logger.info(f"source foundURL: {source_url}, Starting re-download")
                    
                    # byURLSelect download method by type
                    if 'bilibili.com' in source_url:
                        # BRe-download site video
                        from .bilibili import process_download_task, BilibiliDownloadRequest, BilibiliDownloadTask, download_tasks
                        import uuid
                        
                        # Create download request
                        download_request = BilibiliDownloadRequest(
                            url=source_url,
                            project_name=project.name,
                            video_category=project.project_metadata.get('category', 'general')
                        )
                        
                        # Generating new taskID
                        download_task_id = str(uuid.uuid4())
                        
                        # Creating task record
                        task = BilibiliDownloadTask(
                            id=download_task_id,
                            url=source_url,
                            project_name=project.name,
                            video_category=project.project_metadata.get('category', 'general'),
                            status="pending",
                            progress=0.0,
                            project_id=project_id,
                            created_at=str(uuid.uuid1().time),
                            updated_at=str(uuid.uuid1().time)
                        )
                        
                        # Store task
                        download_tasks[download_task_id] = task
                        
                        # Asynchronously start download task
                        from .async_task_manager import task_manager
                        await task_manager.create_safe_task(
                            f"bilibili_redownload_{download_task_id}",
                            process_download_task,
                            download_task_id,
                            download_request,
                            project_id
                        )
                        
                        return {
                            "message": "Video file not found; started re-downloadBSite video",
                            "project_id": project_id,
                            "download_task_id": download_task_id,
                            "source_url": source_url
                        }
                    elif 'youtube.com' in source_url or 'youtu.be' in source_url:
                        # YouTubeVideo re-download
                        from .youtube import process_youtube_download_task, YouTubeDownloadRequest
                        import uuid
                        
                        # Create download request
                        download_request = YouTubeDownloadRequest(
                            url=source_url,
                            project_name=project.name,
                            video_category=project.project_metadata.get('category', 'general')
                        )
                        
                        # Generating new taskID
                        download_task_id = str(uuid.uuid4())
                        
                        # Import task model and storage dictionary
                        from .youtube import YouTubeDownloadTask, download_tasks
                        task = YouTubeDownloadTask(
                            id=download_task_id,
                            url=source_url,
                            project_name=project.name,
                            video_category=project.project_metadata.get('category', 'general') if hasattr(project, 'project_metadata') and project.project_metadata else 'general',
                            status="pending",
                            progress=0.0,
                            project_id=project_id,
                            created_at=str(uuid.uuid1().time),
                            updated_at=str(uuid.uuid1().time)
                        )
                        download_tasks[download_task_id] = task

                        # Asynchronously start download task
                        from .async_task_manager import task_manager
                        await task_manager.create_safe_task(
                            f"youtube_redownload_{download_task_id}",
                            process_youtube_download_task,
                            download_task_id,
                            download_request,
                            project_id
                        )
                        
                        return {
                            "message": "Video file not found; started re-downloadYouTubevideo",
                            "project_id": project_id,
                            "download_task_id": download_task_id,
                            "source_url": source_url
                        }
                    else:
                        raise HTTPException(status_code=400, detail=f"Unsupported video source: {source_url}")
                else:
                    raise HTTPException(status_code=400, detail=f"Video file does not exist and has no sourceURL: {video_path}")
            else:
                raise HTTPException(status_code=400, detail=f"Video file not found and no project metadata exists: {video_path}")
        
        # Subtitle file is optional
        srt_path_str = str(srt_path) if srt_path.exists() else None
        
        # Lazy import to avoid triggering too earlycelery_appimport chain
        from backend.tasks.processing import process_video_pipeline
        
        # SubmitCeleryTask - Using string typeproject_id
        celery_task = process_video_pipeline.delay(
            project_id=project_id,
            input_video_path=str(video_path),
            input_srt_path=srt_path_str
        )
        
        # Create new processing task record
        from ...models.task import TaskType
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type=TaskType.VIDEO_PROCESSING
        )
        
        # Updating task'sCelerytaskID
        task_result.celery_task_id = celery_task.id
        processing_service.db.commit()
        
        return {
            "message": "Processing retry started successfully",
            "project_id": project_id,
            "task_id": task_result.id,
            "celery_task_id": celery_task.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Sending error notification - DisabledWebSocketNotify
        # try:
        #     await websocket_service.send_processing_error(
        #         project_id=int(project_id),
        #         error=str(e),
        #         step="retry_initialization"
        #     )
        # except:
        #     pass
        logger.exception("Retry failed project processing: %s", project_id)
        raise HTTPException(status_code=500, detail="Retrying failed processing, please try again later")


@router.post("/{project_id}/resume")
async def resume_processing(
    project_id: str,
    start_step: str = Form(..., description="Step to resume from (step1_outline, step2_timeline, etc.)"),
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Resume processing from a specific step."""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check project status
        if project.status.value not in ["failed", "processing", "pending"]:
            raise HTTPException(status_code=400, detail="Project is not in failed, processing, or pending status")
        
        # getSRTFile path (if applicable))
        srt_path = None
        if start_step == "step1_outline":
            if project.processing_config and "srt_file" in project.processing_config:
                from pathlib import Path
                project_root = Path(__file__).parent.parent.parent / "data" / "projects" / project_id
                srt_path = project_root / "raw" / project.processing_config["srt_file"]
            
            if not srt_path or not srt_path.exists():
                raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
        # Resume execution by calling handler service
        result = processing_service.resume_processing(project_id, start_step, srt_path)
        
        return {
            "message": f"Processing resumed from {start_step} successfully",
            "project_id": project_id,
            "start_step": start_step,
            "result": result
        }
    except Exception as e:
        logger.exception("Failed to resume project processing: %s", project_id)
        raise HTTPException(status_code=500, detail="Recovery failed. Please try again later")


@router.get("/{project_id}/status")
async def get_processing_status(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Get real-time, unified processing status and progress for a project."""
    try:
        from backend.core.progress_tracker import get_progress
        from backend.models.project import ProjectStatus

        # 1. Fetch project
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # 2. Check live in-memory progress tracker (real-time heartbeat and logs)
        live_prog = get_progress(project_id)

        # 3. Check latest task in database
        tasks = project.tasks if hasattr(project, 'tasks') else []
        latest_task = None
        if tasks:
            latest_task = max(tasks, key=lambda t: t.created_at) if hasattr(tasks[0], 'created_at') else tasks[0]

        # 4. Handle completed state
        if project.status == ProjectStatus.COMPLETED:
            return {
                "status": "completed",
                "current_step": 6,
                "total_steps": 6,
                "step_name": "Video Processing Completed",
                "substep": "All clips rendered and saved successfully",
                "progress": 100.0,
                "is_alive": False,
                "elapsed_seconds": live_prog.get("elapsed_seconds", 0) if live_prog else 0,
                "recent_logs": live_prog.get("recent_logs", []) if live_prog else [],
                "error_message": None
            }

        # 5. Handle failed state
        if project.status == ProjectStatus.FAILED:
            cfg = project.processing_config or {}
            err_msg = None
            if live_prog and live_prog.get("error_message"):
                err_msg = live_prog["error_message"]
            elif latest_task and latest_task.error_message:
                err_msg = latest_task.error_message
            elif cfg.get("error_message"):
                err_msg = cfg.get("error_message")
            if not err_msg:
                err_msg = "Video processing encountered an error"

            return {
                "status": "error",
                "current_step": live_prog.get("current_step", 0) if live_prog else 0,
                "total_steps": 6,
                "step_name": "Processing Failed",
                "substep": err_msg,
                "progress": live_prog.get("overall_percent", 0.0) if live_prog else 0.0,
                "is_alive": False,
                "recent_logs": live_prog.get("recent_logs", []) if live_prog else [],
                "error_message": err_msg
            }

        # 6. Handle active live progress tracker
        if live_prog and live_prog.get("status") == "running":
            overall_pct = float(live_prog.get("overall_percent", 0.0))
            return {
                "status": "processing",
                "current_step": int(live_prog.get("current_step", 0)),
                "total_steps": int(live_prog.get("total_steps", 6)),
                "step_name": live_prog.get("step_name", "Processing video..."),
                "substep": live_prog.get("substep", ""),
                "progress": max(1.0, min(99.0, overall_pct)),
                "step_percent": float(live_prog.get("step_percent", 0.0)),
                "is_alive": bool(live_prog.get("is_alive", True)),
                "elapsed_seconds": float(live_prog.get("elapsed_seconds", 0)),
                "recent_logs": live_prog.get("recent_logs", []),
                "error_message": None
            }

        # 7. Handle downloading / preparation in pending status
        cfg = project.processing_config or {}
        download_status = cfg.get("download_status")
        if download_status == "downloading":
            dl_progress = float(cfg.get("download_progress", 0.0) or 0.0)
            dl_msg = cfg.get("download_message", "Downloading video...")
            return {
                "status": "processing",
                "current_step": 0,
                "total_steps": 6,
                "step_name": f"📥 {dl_msg}",
                "substep": f"Download progress: {dl_progress:.1f}%",
                "progress": dl_progress,
                "is_alive": True,
                "error_message": None
            }

        # 8. Handle database processing task
        if project.status == ProjectStatus.PROCESSING:
            from backend.models.task import TaskStatus
            if latest_task and latest_task.status in [TaskStatus.FAILED, "failed", "error"]:
                err_msg = latest_task.error_message or "Video processing task failed"
                return {
                    "status": "error",
                    "current_step": 1,
                    "total_steps": 6,
                    "step_name": "Processing Failed",
                    "substep": err_msg,
                    "progress": 0.0,
                    "is_alive": False,
                    "elapsed_seconds": 0,
                    "recent_logs": live_prog.get("recent_logs", []) if live_prog else [],
                    "error_message": err_msg
                }
            prog_val = float(latest_task.progress if (latest_task and latest_task.progress) else 10.0)
            step_str = str(latest_task.current_step if (latest_task and latest_task.current_step) else "Processing pipeline...")
            return {
                "status": "processing",
                "current_step": 1,
                "total_steps": 6,
                "step_name": step_str,
                "substep": "Processing video frames and audio",
                "progress": max(5.0, min(99.0, prog_val)),
                "is_alive": True,
                "elapsed_seconds": 0,
                "recent_logs": [],
                "error_message": None
            }

        # 9. Default pending state
        return {
            "status": "pending",
            "current_step": 0,
            "total_steps": 6,
            "step_name": "Queued",
            "substep": "Waiting to start processing",
            "progress": 0.0,
            "is_alive": False,
            "recent_logs": [],
            "error_message": None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get processing status: %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve processing status, please try again later")


@router.post("/{project_id}/reveal")
async def reveal_project_folder(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Reveal the project folder or output directory in native OS file manager (Finder / Explorer / Nautilus)."""
    from ...core.path_utils import get_project_directory, get_project_output_directory, reveal_in_file_manager

    project = project_service.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    proj_dir = get_project_directory(project_id)
    out_dir = get_project_output_directory(project_id)

    # Prefer output folder if it exists, otherwise project directory
    target = out_dir if (out_dir.exists() and any(out_dir.iterdir())) else proj_dir
    success = reveal_in_file_manager(target)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to open system file explorer")
    return {"success": True, "path": str(target)}


@router.get("/{project_id}/logs")
async def get_project_logs(
    project_id: str,
    lines: int = Query(50, ge=1, le=1000, description="Number of log lines to return"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get real, structured execution logs for a project."""
    try:
        from backend.core.path_utils import get_project_directory, get_log_file_path
        from backend.core.progress_tracker import get_progress
        import re

        log_entries = []

        # 1. Read from project's dedicated processing.log if available
        proj_dir = get_project_directory(project_id)
        proj_log = proj_dir / "processing.log"
        if proj_log.exists():
            try:
                raw_lines = proj_log.read_text(encoding="utf-8", errors="ignore").splitlines()
                for line in raw_lines[-lines:]:
                    parts = line.split(" - ", 3)
                    if len(parts) == 4:
                        log_entries.append({
                            "timestamp": parts[0].strip(),
                            "module": parts[1].strip(),
                            "level": parts[2].strip(),
                            "message": parts[3].strip()
                        })
                    else:
                        log_entries.append({
                            "timestamp": "",
                            "module": "pipeline",
                            "level": "INFO",
                            "message": line.strip()
                        })
            except Exception as e:
                logger.warning(f"Failed to read project log file: {e}")

        # 2. Check live progress recent_logs buffer
        live_prog = get_progress(project_id)
        if live_prog and live_prog.get("recent_logs"):
            for entry in live_prog["recent_logs"]:
                m = re.match(r"^\[(.*?)\]\s*(.*)$", entry)
                ts = m.group(1) if m else ""
                msg = m.group(2) if m else entry
                if not any(e["message"] == msg for e in log_entries):
                    log_entries.append({
                        "timestamp": ts,
                        "module": "pipeline",
                        "level": "INFO",
                        "message": msg
                    })

        # 3. If still empty, scan global backend.log for this project_id
        if not log_entries:
            global_log = get_log_file_path()
            if global_log.exists():
                try:
                    with open(global_log, "r", encoding="utf-8", errors="ignore") as f:
                        file_lines = f.readlines()
                    matched = [l.strip() for l in file_lines if project_id in l]
                    for l in matched[-lines:]:
                        parts = l.split(" - ", 3)
                        if len(parts) == 4:
                            log_entries.append({
                                "timestamp": parts[0].strip(),
                                "module": parts[1].strip(),
                                "level": parts[2].strip(),
                                "message": parts[3].strip()
                            })
                        else:
                            log_entries.append({
                                "timestamp": "",
                                "module": "backend",
                                "level": "INFO",
                                "message": l
                            })
                except Exception:
                    pass

        # 4. If still no logs, create clear initial lifecycle status
        if not log_entries:
            proj = project_service.get(project_id)
            if proj:
                created_iso = proj.created_at.isoformat() if proj.created_at else ""
                log_entries.append({
                    "timestamp": created_iso,
                    "module": "project",
                    "level": "INFO",
                    "message": f"Project '{proj.name}' initialized in database (Status: {proj.status.value})"
                })

        return {"logs": log_entries[-lines:]}
    except Exception as e:
        logger.exception("Failed to get project logs: %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve project logs, please try again later")



@router.get("/{project_id}/import-status")
async def get_import_status(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Getting import status of project"""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Checking for an ongoing import task
        from backend.celery_app import celery_app
        
        # Here you can add more complex task state check logic
        # Returns current project status
        return {
            "project_id": project_id,
            "status": project.status.value,
            "message": "Import status normal"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get import status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get import status: {str(e)}")


@router.post("/{project_id}/generate-thumbnail")
async def generate_project_thumbnail(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Generating thumbnail for project"""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check for video file
        if not project.video_path:
            raise HTTPException(status_code=400, detail="Project has no video file")
        
        # Check if video file exists
        video_path = Path(project.video_path)
        if not video_path.exists():
            raise HTTPException(status_code=400, detail="Video file not found")
        
        # Generating thumbnail
        from ...utils.thumbnail_generator import generate_project_thumbnail
        thumbnail_data = generate_project_thumbnail(project_id, video_path)
        
        if thumbnail_data:
            # Save thumbnail to database
            project.thumbnail = thumbnail_data
            project_service.db.commit()
            
            return {
                "success": True,
                "thumbnail": thumbnail_data,
                "message": "Thumbnail generated and saved successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Thumbnail generation failed")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate project thumbnail: {e}")
        raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {str(e)}")


@router.api_route("/{project_id}/files/{filename}", methods=["GET", "HEAD"])
async def get_project_file(
    project_id: str,
    filename: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a project file by filename."""
    try:
        from pathlib import Path
        import json
        from fastapi.responses import FileResponse
        
        # Build file path - use correct project directory path
        from ...core.path_utils import get_project_directory
        project_root = get_project_directory(project_id)
        
        filename_base = Path(filename).name
        # Trying multiple possible paths
        possible_paths = [
            project_root / "raw" / filename,  # Original file
            project_root / "raw" / filename_base,
            project_root / "metadata" / filename,  # Metadata file
            project_root / "metadata" / filename_base,
            project_root / filename,  # Directly in project root directory
            project_root / filename_base,
        ]
        
        file_path = None
        for path in possible_paths:
            if path.exists() and path.is_file():
                file_path = path
                break
        
        if not file_path:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Return different response based on file type
        if filename.endswith('.json'):
            # JSONFile returned data
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        else:
            # Other files (such as videos) return file stream
            media_type = "video/mp4" if filename.endswith('.mp4') else "application/octet-stream"
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type=media_type,
                headers={
                    "Accept-Ranges": "bytes",  # Support range requests for video playback
                    "Cache-Control": "public, max-age=3600"  # cache1Hours
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get project file: %s/%s", project_id, filename)
        raise HTTPException(status_code=500, detail="Failed to retrieve project file, please try again later")


@router.get("/{project_id}/clips/{clip_id}")
async def get_project_clip(
    project_id: str,
    clip_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a specific clip video file for a project."""
    try:
        from pathlib import Path
        import os
        
        # Build video file path - use correct project directory path
        from ...core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"
        
        # Ensuring path exists
        if not clips_dir.exists():
            raise HTTPException(status_code=404, detail=f"Clips directory not found: {clips_dir}")
        
        # Find corresponding video file
        # First trying throughclip_idFind
        video_files = list(clips_dir.glob(f"{clip_id}_*.mp4"))
        
        # If not found, attempt to find allmp4File, then match through database
        if not video_files:
            from ...models.clip import Clip
            clip = project_service.db.query(Clip).filter(Clip.id == clip_id).first()
            if clip and clip.video_path:
                video_file_path = Path(clip.video_path)
                if video_file_path.exists():
                    video_file = video_file_path
                else:
                    raise HTTPException(status_code=404, detail=f"Clip video file not found for clip_id: {clip_id}")
            else:
                raise HTTPException(status_code=404, detail=f"Clip not found in database: {clip_id}")
        else:
            video_file = video_files[0]
        
        # Check if file exists
        if not video_file.exists():
            raise HTTPException(status_code=404, detail="Clip video file not found")
        
        # Returning file stream
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(video_file),
            media_type="video/mp4",
            filename=video_file.name,
            headers={
                "Cache-Control": "no-cache, must-revalidate",
                "Pragma": "no-cache"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Getting slice retrieval failed: %s/%s", project_id, clip_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve slice file, please try again later")


@router.post("/sync-all")
async def sync_all_projects_from_filesystem(
    db: Session = Depends(get_db)
):
    """Synchronize all project data from file system to database"""
    try:
        from backend.services.data_sync_service import DataSyncService
        from backend.core.config import get_data_directory
        
        # Getting data directory
        data_dir = get_data_directory()
        
        # Create data synchronization service
        sync_service = DataSyncService(db)
        
        # Synchronizing all projects
        result = sync_service.sync_all_projects_from_filesystem(data_dir)
        
        return {
            "success": result.get("success", False),
            "message": "Data synchronization complete",
            "synced_projects": result.get("synced_projects", []),
            "failed_projects": result.get("failed_projects", []),
            "total_synced": len(result.get("synced_projects", [])),
            "total_failed": len(result.get("failed_projects", []))
        }
        
    except Exception as e:
        logger.error(f"Failed to synchronize all project data: {e}")
        raise HTTPException(status_code=500, detail=f"Synchronization failed: {str(e)}")


@router.patch("/{project_id}/collections/{collection_id}/reorder")
async def reorder_collection_clips(
    project_id: str,
    collection_id: str,
    clip_ids: List[str],
    db: Session = Depends(get_db)
):
    """Reorder slices in collection"""
    try:
        from backend.services.collection_service import CollectionService
        
        # Create collection service
        collection_service = CollectionService(db)
        
        # Get collection
        collection = collection_service.get(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # Verify collection belongs to specified project
        if str(collection.project_id) != project_id:
            raise HTTPException(status_code=400, detail="Collection does not belong to the specified project")
        
        # Updatecollection_metadatainclip_ids
        metadata = getattr(collection, 'collection_metadata', {}) or {}
        metadata['clip_ids'] = clip_ids
        
        # Directly update databasecollection_metadatafield
        from sqlalchemy import update
        from backend.models.collection import Collection
        
        stmt = update(Collection).where(Collection.id == collection_id).values(
            collection_metadata=metadata
        )
        collection_service.db.execute(stmt)
        collection_service.db.commit()
        
        return {
            "message": "Collection clips reordered successfully",
            "clip_ids": clip_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reordering collection {collection_id} Slice failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reordering failed: {str(e)}")


@router.post("/sync/{project_id}")
async def sync_project_from_filesystem(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Synchronize specified project data from file system to database"""
    try:
        from backend.services.data_sync_service import DataSyncService
        from backend.core.config import get_data_directory
        
        # Getting data directory
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail=f"Project directory does not exist: {project_id}")
        
        # Create data synchronization service
        sync_service = DataSyncService(db)
        
        # Synchronizing project data
        result = sync_service.sync_project_from_filesystem(project_id, project_dir)
        
        return {
            "success": result.get("success", False),
            "project_id": project_id,
            "clips_synced": result.get("clips_synced", 0),
            "collections_synced": result.get("collections_synced", 0),
            "message": f"project {project_id} Synchronization complete"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Synchronize project {project_id} Data failed: {e}")
        raise HTTPException(status_code=500, detail=f"Synchronization failed: {str(e)}")


@router.post("/{project_id}/collections/{collection_id}/generate")
async def generate_collection_video(
    project_id: str,
    collection_id: str,
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """Generating collection video"""
    try:
        from ...models.collection import Collection
        from ...models.clip import Clip
        from ...utils.video_processor import VideoProcessor
        from ...core.path_utils import get_project_directory
        from pathlib import Path
        import json
        
        # Validate if project exists
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Getting collection record
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection does not exist")
        
        # Verify collection belongs to this project
        if str(collection.project_id) != project_id:
            raise HTTPException(status_code=400, detail="Collection does not belong to specified project")
        
        # Get slices from collectionIDlist
        metadata = getattr(collection, 'collection_metadata', {}) or {}
        clip_ids = metadata.get('clip_ids', [])
        
        if not clip_ids:
            raise HTTPException(status_code=400, detail="Collection contains no slices")
        
        # Get slice info, then byclip_idsOrdered by sequence
        clips_dict = {clip.id: clip for clip in db.query(Clip).filter(Clip.id.in_(clip_ids)).all()}
        if len(clips_dict) != len(clip_ids):
            raise HTTPException(status_code=400, detail="Some slices do not exist")
        
        # Get ordered by user adjustmentsclips
        ordered_clips = [clips_dict[clip_id] for clip_id in clip_ids if clip_id in clips_dict]
        
        # Getting project directory
        project_dir = get_project_directory(project_id)
        collections_dir = project_dir / "output" / "collections"
        collections_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare sliced video file paths, in user-adjusted order
        clips_dir = project_dir / "output" / "clips"
        clip_video_paths = []
        
        for clip in ordered_clips:
            if clip.video_path and Path(clip.video_path).exists():
                clip_video_paths.append(Path(clip.video_path))
            else:
                # try inclipsSearching in directory
                possible_paths = [
                    clips_dir / f"{clip.id}_*.mp4",
                    clips_dir / f"clip_{clip.id}.mp4",
                    clips_dir / f"{clip.id}.mp4"
                ]
                
                found = False
                for pattern in possible_paths:
                    if pattern.name.endswith('*'):
                        # Processing wildcard
                        matches = list(clips_dir.glob(pattern.name))
                        if matches:
                            clip_video_paths.append(matches[0])
                            found = True
                            break
                    else:
                        if pattern.exists():
                            clip_video_paths.append(pattern)
                            found = True
                            break
                
                if not found:
                    raise HTTPException(status_code=404, detail=f"Slice video file does not exist: {clip.id}")
        
        # Build collection video file name - use collection title as file name
        collection_name = collection.name or f"collection_{collection_id}"
        # usingVideoProcessorOf / 'ssanitize_filenameClean method for file name
        from ...utils.video_processor import VideoProcessor
        safe_name = VideoProcessor.sanitize_filename(collection_name)
        output_filename = f"{safe_name}.mp4"
        output_path = collections_dir / output_filename
        
        # usingVideoProcessorCreate collection
        video_processor = VideoProcessor(
            clips_dir=str(clips_dir),
            collections_dir=str(collections_dir)
        )
        success = video_processor.create_collection(clip_video_paths, output_path)
        
        if not success:
            raise HTTPException(status_code=500, detail="Collection video generation failed")
        
        # Generate collection cover
        thumbnail_path = None
        try:
            thumbnail_filename = f"{collection_id}_{safe_name}_thumbnail.jpg"
            thumbnail_path = collections_dir / thumbnail_filename
            
            # Extract cover from video (frame5frame seconds)
            thumbnail_success = video_processor.extract_thumbnail(output_path, thumbnail_path, time_offset=5)
            if thumbnail_success:
                collection.thumbnail_path = str(thumbnail_path)
                logger.info(f"Collection cover generation successful: {thumbnail_path}")
            else:
                logger.warning(f"Failed to generate collection cover: {collection_id}")
        except Exception as e:
            logger.error(f"Error generating collection thumbnail: {e}")
        
        # Update collection ofexport_path
        collection.export_path = str(output_path)
        db.commit()
        
        return {
            "success": True,
            "message": "Collection video generation successful",
            "collection_id": collection_id,
            "output_path": str(output_path),
            "filename": output_filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create collection video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection video: {str(e)}")


@router.api_route("/{project_id}/download", methods=["GET", "HEAD"])
async def download_project_file(
    project_id: str,
    clip_id: Optional[str] = Query(None, description="Download specified slice"),
    collection_id: Optional[str] = Query(None, description="Downloading specified collection"),
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """Downloading project file (slice or bundle))"""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        import urllib.parse
        from ...utils.video_processor import VideoProcessor
        from ...core.path_utils import find_clip_video_file, find_collection_video_file
        
        # Validate if project exists
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        if collection_id:
            # Downloading collection video
            file_path, collection = find_collection_video_file(project_id, collection_id, db=db)
            if not file_path or not file_path.exists():
                raise HTTPException(status_code=404, detail="Collection video file does not exist")
            
            # Generate download file name
            collection_name = (collection.name if collection else None) or file_path.stem or f"collection_{collection_id}"
            safe_name = VideoProcessor.sanitize_filename(collection_name)
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
        
        elif clip_id:
            # Downloading clip video
            file_path, clip = find_clip_video_file(project_id, clip_id, db=db)
            if not file_path or not file_path.exists():
                raise HTTPException(status_code=404, detail="Slice video file does not exist")
            
            # Generate download file name
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
        
        else:
            raise HTTPException(status_code=400, detail="Must specify clip_id or collection_id")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.api_route("/{project_id}/export-zip", methods=["GET", "HEAD"])
async def export_project_clips_zip(
    project_id: str,
    platform: Optional[str] = Query(None, description="Filter clips by platform (tiktok, instagram, youtube_shorts, facebook, all)"),
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """Package all clips and subtitles of a project into a downloadable ZIP archive."""
    try:
        import zipfile
        import io
        import json
        import os
        from fastapi.responses import StreamingResponse
        from pathlib import Path
        import urllib.parse
        from ...models.clip import Clip
        from ...utils.video_processor import VideoProcessor
        from ...core.path_utils import get_project_directory, find_clip_video_file

        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        if not clips:
            raise HTTPException(status_code=404, detail="No clips found for this project")

        req_platform = str(platform).lower().strip() if platform else None
        if req_platform in ("youtube", "shorts", "yt"):
            req_platform = "youtube_shorts"
        elif req_platform in ("ig", "reels"):
            req_platform = "instagram"
        elif req_platform in ("fb",):
            req_platform = "facebook"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_STORED) as zip_file:
            for idx, clip in enumerate(clips, 1):
                title = clip.title or clip.generated_title or f"clip_{idx}"
                safe_title = VideoProcessor.sanitize_filename(f"{idx:02d}_{title}")
                
                meta = getattr(clip, 'clip_metadata', {}) or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                cta_plats = meta.get("cta_platforms") or meta.get("platform_videos") or {}

                # If specific platform requested:
                if req_platform and req_platform in ("tiktok", "instagram", "youtube_shorts", "facebook"):
                    target_file = None
                    if isinstance(cta_plats, dict) and req_platform in cta_plats:
                        p = Path(cta_plats[req_platform])
                        if p.exists() and p.stat().st_size > 0:
                            target_file = p
                    if not target_file:
                        file_path, _ = find_clip_video_file(project_id, clip.id, clip_obj=clip, db=db)
                        if file_path and file_path.exists():
                            target_file = file_path

                    if target_file and target_file.exists():
                        zip_file.write(target_file, arcname=f"clips/{safe_title}_{req_platform}.mp4")
                        clip_srt = target_file.with_suffix(".srt")
                        if not clip_srt.exists():
                            orig_path, _ = find_clip_video_file(project_id, clip.id, clip_obj=clip, db=db)
                            if orig_path:
                                clip_srt = orig_path.with_suffix(".srt")
                        if clip_srt and clip_srt.exists():
                            zip_file.write(clip_srt, arcname=f"subtitles/{safe_title}.srt")

                # If "all" or multi-platform files exist:
                elif isinstance(cta_plats, dict) and any(os.path.exists(p) for p in cta_plats.values()):
                    for plat_name, plat_path in cta_plats.items():
                        pp = Path(plat_path)
                        if pp.exists() and pp.stat().st_size > 0:
                            zip_file.write(pp, arcname=f"clips/{plat_name}/{safe_title}_{plat_name}.mp4")
                    orig_path, _ = find_clip_video_file(project_id, clip.id, clip_obj=clip, db=db)
                    if orig_path and orig_path.with_suffix(".srt").exists():
                        zip_file.write(orig_path.with_suffix(".srt"), arcname=f"subtitles/{safe_title}.srt")

                # Fallback to single video path
                else:
                    file_path, _ = find_clip_video_file(project_id, clip.id, clip_obj=clip, db=db)
                    if file_path and file_path.exists():
                        zip_file.write(file_path, arcname=f"clips/{safe_title}.mp4")
                        clip_srt = file_path.with_suffix(".srt")
                        if clip_srt.exists():
                            zip_file.write(clip_srt, arcname=f"subtitles/{safe_title}.srt")

            # Add source subtitle file if available
            proj_dir = get_project_directory(project_id)
            srt_path = proj_dir / "raw" / "input.srt"
            if srt_path.exists():
                safe_pname = VideoProcessor.sanitize_filename(project.name)
                zip_file.write(srt_path, arcname=f"{safe_pname}_full_subtitles.srt")

        zip_buffer.seek(0)
        safe_proj_name = VideoProcessor.sanitize_filename(project.name)
        plat_suffix = f"_{req_platform}" if req_platform and req_platform != "all" else "_all_platforms"
        archive_name = f"{safe_proj_name}{plat_suffix}_clips.zip"
        encoded_name = urllib.parse.quote(archive_name.encode('utf-8'))

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
                "Content-Type": "application/zip"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export clips zip: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create ZIP package: {str(e)}")


@router.get("/{project_id}/collections/{collection_id}/thumbnail")
async def get_collection_thumbnail(
    project_id: str,
    collection_id: str,
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """Getting collection cover image"""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        
        # Validate if project exists
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Getting collection record
        from ...models.collection import Collection
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection does not exist")
        
        # Verify collection belongs to this project
        if str(collection.project_id) != project_id:
            raise HTTPException(status_code=400, detail="Collection does not belong to specified project")
        
        # Check for cover image
        if not collection.thumbnail_path:
            raise HTTPException(status_code=404, detail="Collection cover does not exist")
        
        thumbnail_path = Path(collection.thumbnail_path)
        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="Collection cover file does not exist")
        
        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600"  # cache1Hours
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection cover: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collection cover: {str(e)}")