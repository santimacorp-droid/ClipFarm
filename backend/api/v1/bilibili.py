"""
BSite relatedAPIRoute processingBSite video parsing and download function
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from pydantic import BaseModel
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from ...utils.bilibili_downloader import BilibiliDownloader, get_bilibili_video_info
from ...core.config import get_data_directory
from pathlib import Path
import uuid
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# Storing download task state
download_tasks = {}

class BilibiliParseRequest(BaseModel):
    url: str
    browser: Optional[str] = None

class BilibiliDownloadRequest(BaseModel):
    url: str
    project_name: Optional[str] = None
    video_category: Optional[str] = "default"
    browser: Optional[str] = None
    caption_style: Optional[str] = "hormozi_yellow"
    duration_mode: Optional[str] = "tiktok_crp"
    aspect_ratio: Optional[str] = "9:16_blur"
    show_hook_banner: Optional[bool] = True
    watermark_preset_id: Optional[str] = "none"

class BilibiliVideoInfo(BaseModel):
    title: str
    description: str
    duration: int
    uploader: str
    upload_date: str
    view_count: int
    like_count: int
    thumbnail: str

class BilibiliDownloadTask(BaseModel):
    id: str
    url: str
    project_name: str
    video_category: str
    status: str  # pending, processing, completed, failed
    progress: float
    error_message: Optional[str] = None
    project_id: Optional[str] = None
    created_at: str
    updated_at: str

@router.post("/parse")
async def parse_bilibili_video(
    url: str = Form(...),
    browser: Optional[str] = Form(None)
):
    """ParseBSite video information"""
    try:
        logger.info(f"Beginning parsingBSite video: {url}")
        
        # ValidateURLFormat
        downloader = BilibiliDownloader(browser=browser)
        if not downloader.validate_bilibili_url(url):
            raise HTTPException(status_code=400, detail="InvalidBSite video link")
        
        # Getting real video information
        video_info = await downloader.get_video_info(url)
        
        logger.info(f"Video information parsed successfully: {video_info.title}")
        
        return {
            "success": True,
            "video_info": {
                "title": video_info.title,
                "description": video_info.description,
                "duration": video_info.duration,
                "uploader": video_info.uploader,
                "upload_date": video_info.upload_date,
                "view_count": video_info.view_count,
                "like_count": 0,  # BSiteAPIMay not provide like count
                "thumbnail": video_info.thumbnail_url
            }
        }
        
    except Exception as e:
        logger.error(f"ParseBSite video failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

@router.post("/download")
async def create_bilibili_download_task(request: BilibiliDownloadRequest):
    """CreateBSite video download task — creates project immediately"""
    try:
        logger.info(f"CreateBSite download task: {request.url}")
        
        # First get video info to obtain thumbnail
        from ...utils.bilibili_downloader import BilibiliDownloader
        downloader = BilibiliDownloader(browser=request.browser)
        video_info = await downloader.get_video_info(request.url)
        
        # Immediately create project record
        from ...core.database import SessionLocal
        from ...services.project_service import ProjectService
        from ...schemas.project import ProjectCreate, ProjectType, ProjectStatus
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # Handle thumbnail – directly uses thumbnail extracted from video
            thumbnail_data = None
            if video_info.thumbnail_url:
                try:
                    import requests
                    import base64
                    
                    # Download thumbnail
                    response = requests.get(video_info.thumbnail_url, timeout=10)
                    if response.status_code == 200:
                        # Convert tobase64
                        thumbnail_base64 = base64.b64encode(response.content).decode('utf-8')
                        thumbnail_data = f"data:image/jpeg;base64,{thumbnail_base64}"
                        logger.info(f"BSite thumbnail obtained successfully: {video_info.title}")
                    else:
                        logger.warning(f"DownloadBFailed to get site thumbnail: {response.status_code}")
                except Exception as e:
                    logger.error(f"ProcessBFailed to get site thumbnail: {e}")
                    # Thumbnail processing failure does not affect main flow
            
            # Determining project name
            resolved_project_name = (request.project_name or '').strip() or video_info.title or f"Bilibili_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Creating project data
            project_data = ProjectCreate(
                name=resolved_project_name,
                description=f"Downloaded from Bilibili: {video_info.title}",
                project_type=ProjectType(request.video_category),
                status=ProjectStatus.PENDING,  # Initial state is pending
                source_url=request.url,
                source_file=None,  # Temporarily empty, updated after download completion
                settings={
                    "download_status": "downloading",
                    "download_progress": 0.0,
                    "caption_style": request.caption_style or "hormozi_yellow",
                    "duration_mode": request.duration_mode or "tiktok_crp",
                    "aspect_ratio": request.aspect_ratio or "9:16_blur",
                    "show_hook_banner": True if request.show_hook_banner is None else request.show_hook_banner,
                    "watermark_preset_id": request.watermark_preset_id or "none",
                    "bilibili_info": {
                        "url": request.url,
                        "browser": request.browser,
                        "title": video_info.title,
                        "uploader": video_info.uploader,
                        "duration": video_info.duration,
                        "view_count": video_info.view_count,
                        "thumbnail_url": video_info.thumbnail_url
                    }
                }
            )
            
            project = project_service.create_project(project_data)
            project_id = str(project.id)
            
            # Set thumbnail
            if thumbnail_data:
                project.thumbnail = thumbnail_data
                db.commit()
                logger.info(f"Project {project_id} Thumbnail set")
            
            # Creating project directory
            from ...core.path_utils import get_project_directory
            project_dir = get_project_directory(project_id)
            raw_dir = project_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Project created: {project_id}")
            
            # Generating download tasksID
            task_id = str(uuid.uuid4())
            
            # Creating task record
            task = BilibiliDownloadTask(
                id=task_id,
                url=request.url,
                project_name=resolved_project_name,
                video_category=request.video_category,
                status="pending",
                progress=0.0,
                project_id=project_id,  # Link projectID
                created_at=str(uuid.uuid1().time),
                updated_at=str(uuid.uuid1().time)
            )
            
            # Store task
            download_tasks[task_id] = task
            
            # Async start download task – uses safe task manager
            from .async_task_manager import task_manager
            await task_manager.create_safe_task(
                f"bilibili_download_{task_id}", 
                process_download_task, 
                task_id, 
                request, 
                project_id
            )
            
            # Return project information instead of task information
            return {
                "project_id": project_id,
                "task_id": task_id,
                "status": "created",
                "message": "Project created, downloading..."
            }
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Failed to create download task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.get("/tasks/{task_id}")
async def get_bilibili_task_status(task_id: str):
    """Get download task status"""
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return download_tasks[task_id]

@router.get("/tasks")
async def get_all_bilibili_tasks():
    """Get all download tasks"""
    return list(download_tasks.values())

async def update_project_download_progress(project_id: str, progress: float, message: str):
    """Update project download progress"""
    try:
        from ...core.database import SessionLocal
        from ...services.project_service import ProjectService
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            project = project_service.get(project_id)
            
            if project:
                from sqlalchemy.orm.attributes import flag_modified
                config = dict(project.processing_config or {})
                config.update({
                    "download_progress": round(progress, 1),
                    "download_message": message,
                    "download_status": "completed" if progress >= 100.0 else "downloading"
                })
                project.processing_config = config
                flag_modified(project, "processing_config")
                
                # If progress reaches100%, Updating status to waiting for processing
                if progress >= 100.0:
                    from ...schemas.project import ProjectStatus
                    project.status = ProjectStatus.PENDING
                
                db.commit()
                logger.info(f"Project {project_id} Download progress updated: {progress}% - {message}")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to update project download progress: {e}")

async def process_download_task(task_id: str, request: BilibiliDownloadRequest, project_id: str):
    """Processing download tasks"""
    try:
        # Updating task status to processing
        download_tasks[task_id].status = "processing"
        download_tasks[task_id].progress = 10.0
        
        # Updating project status and progress
        await update_project_download_progress(project_id, 5.0, "Connecting & fetching video info...")
        
        # Getting video information
        video_info = await get_bilibili_video_info(request.url, request.browser)
        download_tasks[task_id].progress = 10.0
        
        # Updating project progress
        await update_project_download_progress(project_id, 10.0, "Downloading video...")
        
        # Download video
        data_dir = get_data_directory()
        download_dir = data_dir / "temp"
        download_dir.mkdir(exist_ok=True)
        
        from ...utils.bilibili_downloader import download_bilibili_video
        download_result = await download_bilibili_video(
            request.url, 
            download_dir, 
            request.browser
        )
        
        video_path = download_result.get('video_path', '')
        subtitle_path = download_result.get('subtitle_path', '')
        
        # Updating project progress
        await update_project_download_progress(project_id, 85.0, "Video downloaded, preparing subtitles...")
        
        # If no subtitle file exists, use firstWhisperGenerate subtitles
        if not subtitle_path and video_path:
            logger.info("Prefer usingWhisperGenerating high-quality subtitles")
            # Updating project progress
            await update_project_download_progress(project_id, 90.0, "Generating subtitles with Whisper...")
            
            try:
                from ...utils.speech_recognizer import generate_subtitle_for_video, SpeechRecognitionError
                from pathlib import Path
                video_file_path = Path(video_path)
                
                # Select appropriate model based on video info, but always use automatic language detection
                model = "base"  # Default to balanced model
                language = "auto"  # Always use automatic language detection
                
                # Determine content type based on video title or description, then select model size
                if video_info.title and any(keyword in video_info.title.lower() for keyword in ['tutorial', 'teaching', 'knowledge', 'science']):
                    model = "small"  # Knowledge-related content uses a more accurate model
                elif video_info.title and any(keyword in video_info.title.lower() for keyword in ['presentation', 'lecture', 'talk', 'speech']):
                    model = "medium"  # Use high-precision model for presentation content
                
                logger.info(f"Using Whisper for subtitle generation - Language: {language}, Model: {model}")
                
                generated_subtitle = generate_subtitle_for_video(
                    video_file_path,
                    language=language,
                    model=model
                )
                subtitle_path = str(generated_subtitle)
                logger.info(f"WhisperSubtitle generation successful: {subtitle_path}")
                
                # Updating project progress
                await update_project_download_progress(project_id, 90.0, "Subtitle generation complete, preparing for processing...")
                
            except SpeechRecognitionError as e:
                logger.error(f"WhisperSubtitle generation failed: {e}")
                # WhisperMark project as failed status on failure
                logger.error("Caption file does not exist andWhisperGeneration failed, project will be marked as failed status")
                subtitle_path = None  # Ensure subtitle path is empty, will later mark project as failed
            except Exception as e:
                logger.error(f"Unknown error occurred during subtitle generation: {e}")
                subtitle_path = None  # Ensure subtitle path is empty, will later mark project as failed
        
        download_tasks[task_id].progress = 80.0
        
        # Update project information (project was created at beginning))
        from ...services.project_service import ProjectService
        from ...core.database import SessionLocal
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # Get created projects
            project = project_service.get(project_id)
            if not project:
                raise Exception(f"Project {project_id} Not found")
            
            # Updating project information
            project.description = f"FromBSite download: {video_info.title}"
            # Note: Do not set it herevideo_path, Set after file movement completes
            
            # Updating project settings
            if not project.processing_config:
                project.processing_config = {}
            
            project.processing_config.update({
                "bilibili_info": {
                    "title": video_info.title,
                    "uploader": video_info.uploader,
                    "duration": video_info.duration,
                    "view_count": video_info.view_count
                },
                "subtitle_path": subtitle_path if subtitle_path else None,
                "download_status": "completed",
                "download_progress": 100.0
            })
            
            # Moving file to project directory
            from ...core.path_utils import get_project_directory
            project_dir = get_project_directory(project_id)
            raw_dir = project_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            # Move video file to project directory
            import shutil
            from pathlib import Path
            
            if video_path:
                video_file_path = Path(video_path)
                if video_file_path.exists():
                    # Rename video file toinput.mp4
                    new_video_path = raw_dir / "input.mp4"
                    shutil.move(str(video_file_path), str(new_video_path))
                    logger.info(f"Video file moved to ...: {new_video_path}")
                    
                    # Updating video path in project
                    project.video_path = str(new_video_path)
            
            # Move subtitle file to project directory
            if subtitle_path and subtitle_path.strip():
                subtitle_file_path = Path(subtitle_path)
                if subtitle_file_path.exists():
                    # Rename caption file toinput.srt
                    new_subtitle_path = raw_dir / "input.srt"
                    shutil.move(str(subtitle_file_path), str(new_subtitle_path))
                    logger.info(f"Moved caption file to: {new_subtitle_path}")
                    
                    # Update subtitle path in project processing configuration
                    if not project.processing_config:
                        project.processing_config = {}
                    project.processing_config["subtitle_path"] = str(new_subtitle_path)
            
            # Save project updates
            db.commit()
            
            # Check if subtitle file exists, mark project as failed if it doesn't exist
            srt_file_path = raw_dir / "input.srt"
            if not srt_file_path.exists():
                logger.error(f"Subtitle file does not exist: {srt_file_path}, Marking project as failed status")
                from ...schemas.project import ProjectStatus
                project.status = ProjectStatus.FAILED
                if not project.processing_config:
                    project.processing_config = {}
                project.processing_config["error_message"] = "Caption file does not exist andWhisperGeneration failed"
                db.commit()
                
                # Updating task status to failed
                download_tasks[task_id].status = "failed"
                download_tasks[task_id].error_message = "Caption file does not exist andWhisperGeneration failed"
                download_tasks[task_id].progress = 0.0
                download_tasks[task_id].project_id = str(project.id)
                download_tasks[task_id].updated_at = datetime.now().isoformat()
                
                # Update project download progress to failure
                await update_project_download_progress(project_id, 0.0, "Download failed: Subtitle file does not exist")
                
                logger.info(f"BSite download task failed: {task_id}, ProjectID: {project.id}, Reason: Subtitle file does not exist")
                return
            
            # Update project download progress to complete
            await update_project_download_progress(project_id, 100.0, "Download complete, preparing to start processing")
            
            # Updating task status
            download_tasks[task_id].status = "completed"
            download_tasks[task_id].progress = 100.0
            download_tasks[task_id].project_id = str(project.id)
            download_tasks[task_id].updated_at = datetime.now().isoformat()
            
            logger.info(f"BSite download task completed: {task_id}, ProjectID: {project.id}")
            
            # Auto start processing flow
            try:
                # Update project status to pending processing
                from ...schemas.project import ProjectStatus
                project.status = ProjectStatus.PENDING  # Set toPENDING, Start automation service
                db.commit()
                
                logger.info(f"BSite project {project.id} Download complete, waits for automation pipeline to start")
                
                # Asynchronously start automation pipeline
                import asyncio
                from ...services.auto_pipeline_service import auto_pipeline_service
                
                # Usingcreate_taskExecute in running event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Create task within already-running event loop
                    task = loop.create_task(
                        auto_pipeline_service.auto_start_pipeline(str(project.id))
                    )
                    # Waiting for task completion
                    pipeline_result = await task
                except RuntimeError:
                    # If no running event loop, create a new one
                    pipeline_result = await auto_pipeline_service.auto_start_pipeline(str(project.id))
                
                if pipeline_result['status'] == 'started':
                    logger.info(f"BSite project {project.id} Automation pipeline started successfully: {pipeline_result}")
                else:
                    logger.warning(f"BSite project {project.id} Automation pipeline startup result: {pipeline_result}")
                
            except Exception as e:
                logger.error(f"StartBSite project {project.id} Automation pipeline failed: {str(e)}")
                # Although processing startup fails, return download success
                # User can restart processing using the retry button
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to process download task: {str(e)}")
        download_tasks[task_id].status = "failed"
        download_tasks[task_id].error_message = str(e)
        download_tasks[task_id].progress = 0.0

        # Also save「Project」Mark as failed — otherwise project will remain in this state indefinitely pending, 
        # The front end will always treat it as「Pending start」Repeat — one of the root causes of previous full-screen errors). 
        try:
            from ...core.database import SessionLocal
            from ...services.project_service import ProjectService
            from ...schemas.project import ProjectStatus
            db = SessionLocal()
            try:
                project_service = ProjectService(db)
                project = project_service.get(project_id)
                if project and project.status == ProjectStatus.PENDING:
                    project.status = ProjectStatus.FAILED
                    if not project.processing_config:
                        project.processing_config = {}
                    project.processing_config["error_message"] = f"Download failed: {e}"
                    db.commit()
                    logger.info(f"Project {project_id} Marked as failed")
            finally:
                db.close()
        except Exception as inner:
            logger.error(f"Mark project {project_id} Error on failure state: {inner}")
