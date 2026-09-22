"""
Enhanced retry mechanism
"""

import logging
import uuid
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.database import get_db
from ...models.project import Project, ProjectStatus
from ...models.task import Task, TaskStatus, TaskType
from ...services.project_service import ProjectService
from ...services.processing_service import ProcessingService
from ...core.config import get_data_directory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retry", tags=["Enhanced Retry"])

class RetryStrategy(str, Enum):
    """Retry strategy enumeration"""
    DOWNLOAD_ONLY = "download_only"      # Only retry download
    PROCESSING_ONLY = "processing_only"  # Only retry processing
    FULL_RETRY = "full_retry"           # Full retry (download+Process)
    SMART_RETRY = "smart_retry"         # Intelligent retry (auto-determine...))

class RetryRequest(BaseModel):
    """Retry request"""
    strategy: Optional[RetryStrategy] = RetryStrategy.SMART_RETRY
    force_redownload: bool = False  # Force re-download?
    browser: Optional[str] = None   # Browser settings (for download...))

class RetryResponse(BaseModel):
    """Retry response"""
    success: bool
    message: str
    strategy_used: RetryStrategy
    project_id: str
    task_id: Optional[str] = None
    download_task_id: Optional[str] = None

def determine_retry_strategy(project: Project, force_redownload: bool = False) -> RetryStrategy:
    """Smartly determine retry strategy"""
    if force_redownload:
        return RetryStrategy.FULL_RETRY
    
    # Check if video file exists
    video_exists = project.video_path and Path(project.video_path).exists()
    
    if not video_exists:
        return RetryStrategy.FULL_RETRY  # No video file, full retry
    
    # Checking project status
    if project.status == ProjectStatus.FAILED:
        return RetryStrategy.PROCESSING_ONLY  # Has video file but processing failed, only reprocess
    elif project.status == ProjectStatus.PENDING:
        return RetryStrategy.PROCESSING_ONLY  # Has video file but not processed, only reprocess
    else:
        return RetryStrategy.SMART_RETRY

async def retry_download_only(
    project_id: str, 
    browser: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Only retry download"""
    try:
        # Getting project information
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Get original download information
        meta = project.project_metadata or {}
        cfg = project.processing_config or {}
        url = meta.get("source_url") or cfg.get("youtube_info", {}).get("url") or cfg.get("bilibili_info", {}).get("url")
        description = project.description or ""
        
        if not url:
            if "FromBSite download:" in description:
                url = description.replace("FromBSite download:", "").strip()
            elif "FromYouTubeDownload:" in description:
                url = description.replace("FromYouTubeDownload:", "").strip()
        
        if url and ("youtube.com" in url or "youtu.be" in url or "FromYouTube" in description):
            return await retry_youtube_download(project_id, url, browser, db)
        elif url and ("bilibili.com" in url or "b23.tv" in url or "FromBSite" in description):
            return await retry_bilibili_download(project_id, url, browser, db)
        else:
            raise HTTPException(status_code=400, detail="Unable to determine download source")
    
    except Exception as e:
        logger.error(f"Download retry failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download retry failed: {str(e)}")

async def retry_bilibili_download(
    project_id: str, 
    url: str, 
    browser: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """RetryBSite download"""
    try:
        # ImportBDownload-related modules
        from .bilibili import process_download_task, BilibiliDownloadRequest
        from .async_task_manager import task_manager
        
        # Creating download request
        request = BilibiliDownloadRequest(
            url=url,
            project_name=db.query(Project).filter(Project.id == project_id).first().name,
            video_category="default",
            browser=browser
        )
        
        # Generate new download taskID
        task_id = str(uuid.uuid4())
        
        # Starting download task
        await task_manager.create_safe_task(
            f"bilibili_retry_{task_id}",
            process_download_task,
            task_id,
            request,
            project_id
        )
        
        return {
            "success": True,
            "message": "BSite download retry initiated",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.error(f"RetryBSite download failed: {e}")
        raise HTTPException(status_code=500, detail=f"RetryBSite download failed: {str(e)}")

async def retry_youtube_download(
    project_id: str, 
    url: str, 
    browser: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """RetryYouTubeDownload"""
    try:
        # ImportYouTubeDownloading related modules
        from .youtube import process_youtube_download_task, YouTubeDownloadRequest
        from .async_task_manager import task_manager
        
        # Creating download request
        request = YouTubeDownloadRequest(
            url=url,
            project_name=db.query(Project).filter(Project.id == project_id).first().name,
            video_category="default",
            browser=browser
        )
        
        # Generate new download taskID
        task_id = str(uuid.uuid4())
        
        # Starting download task
        await task_manager.create_safe_task(
            f"youtube_retry_{task_id}",
            process_youtube_download_task,
            task_id,
            request,
            project_id
        )
        
        return {
            "success": True,
            "message": "YouTubeDownload retry has been initiated",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.error(f"RetryYouTubeDownload failed: {e}")
        raise HTTPException(status_code=500, detail=f"RetryYouTubeDownload failed: {str(e)}")

async def retry_processing_only(
    project_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Only retry processing"""
    try:
        # Use existing process service
        processing_service = ProcessingService(db)
        
        # Getting project information
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Checking video file
        if not project.video_path or not Path(project.video_path).exists():
            raise HTTPException(status_code=400, detail="Video file does not exist, please try downloading again")
        
        # Resetting project status
        project.status = ProjectStatus.PENDING
        db.commit()
        
        # Starting processing task
        result = processing_service.start_processing(
            project_id=project_id,
            srt_path=Path(project.video_path).parent / "input.srt" if (project.video_path and Path(project.video_path).parent / "input.srt").exists() else None
        )
        
        return {
            "success": True,
            "message": "Download retry has been started",
            "task_id": result.get("task_id")
        }
    
    except Exception as e:
        logger.error(f"Retry processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retry processing failed: {str(e)}")

@router.post("/projects/{project_id}/smart-retry", response_model=RetryResponse)
async def smart_retry_project(
    project_id: str,
    request: RetryRequest,
    db: Session = Depends(get_db)
):
    """Smart retry of project"""
    try:
        # Getting project information
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Determining retry strategy
        if request.strategy == RetryStrategy.SMART_RETRY:
            strategy = determine_retry_strategy(project, request.force_redownload)
        else:
            strategy = request.strategy
        
        logger.info(f"Project {project_id} Using retry strategy: {strategy}")
        
        # Executing retry
        if strategy == RetryStrategy.FULL_RETRY:
            # Full retry: download first, then automatically start processing after download completes
            download_result = await retry_download_only(project_id, request.browser, db)
            return RetryResponse(
                success=True,
                message="Full retry initiated (download...+Process)",
                strategy_used=strategy,
                project_id=project_id,
                download_task_id=download_result.get("task_id")
            )
        
        elif strategy == RetryStrategy.DOWNLOAD_ONLY:
            # Only retry download
            download_result = await retry_download_only(project_id, request.browser, db)
            return RetryResponse(
                success=True,
                message="Download retry has been initiated",
                strategy_used=strategy,
                project_id=project_id,
                download_task_id=download_result.get("task_id")
            )
        
        elif strategy == RetryStrategy.PROCESSING_ONLY:
            # Only retry processing
            processing_result = await retry_processing_only(project_id, db)
            return RetryResponse(
                success=True,
                message="Download retry has been started",
                strategy_used=strategy,
                project_id=project_id,
                task_id=processing_result.get("task_id")
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported retry strategy: {strategy}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intelligent retry failed: {e}")
        raise HTTPException(status_code=500, detail=f"Intelligent retry failed: {str(e)}")

@router.get("/projects/{project_id}/retry-strategy")
async def get_retry_strategy(
    project_id: str,
    force_redownload: bool = False,
    db: Session = Depends(get_db)
):
    """Get suggested retry strategy"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        strategy = determine_retry_strategy(project, force_redownload)
        
        return {
            "project_id": project_id,
            "suggested_strategy": strategy,
            "reason": _get_strategy_reason(project, strategy),
            "video_exists": project.video_path and Path(project.video_path).exists(),
            "project_status": project.status
        }
    
    except Exception as e:
        logger.error(f"Failed to retrieve retry strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve retry strategy: {str(e)}")

def _get_strategy_reason(project: Project, strategy: RetryStrategy) -> str:
    """Failed to obtain reason for policy selection"""
    if strategy == RetryStrategy.FULL_RETRY:
        return "No video file or force re-download"
    elif strategy == RetryStrategy.PROCESSING_ONLY:
        return "Video file exists but processing failed or not started"
    elif strategy == RetryStrategy.DOWNLOAD_ONLY:
        return "Retrying only download phase"
    else:
        return "Intelligent judgment"
