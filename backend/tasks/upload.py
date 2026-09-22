"""
Upload-related Celery tasks
"""

import logging
from pathlib import Path
from sqlalchemy.orm import Session

from ..core.celery_app import celery_app
from ..core.database import SessionLocal
from ..services.bilibili_service import BilibiliUploadService
from ..core.path_utils import get_project_output_directory

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='backend.tasks.upload.upload_clip_task')
def upload_clip_task(self, record_id: str, clip_id: str):
    """Upload clip task"""
    db = SessionLocal()
    try:
        logger.info(f"Starting clip upload: record_id={record_id}, clip_id={clip_id}")
        
        # Get upload service
        upload_service = BilibiliUploadService(db)
        
        # Convert record_id to int
        try:
            record_id_int = int(record_id)
        except ValueError:
            raise ValueError(f"Invalid record_id format: {record_id}")
        
        # Get upload record
        upload_record = upload_service.get_upload_record_by_id(record_id_int)
        if not upload_record:
            raise ValueError(f"Upload record does not exist: {record_id}")
        
        # Build video file path
        project_output_dir = get_project_output_directory(str(upload_record.project_id))
        logger.info(f"Project output directory: {project_output_dir}")
        
        # Get clip metadata for file name matching
        from ..models.clip import Clip
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise ValueError(f"Clip record does not exist: {clip_id}")
        
        clip_title = clip.title or clip.generated_title or ""
        logger.info(f"Clip title: {clip_title}")
        
        # Try multiple file naming patterns
        possible_paths = [
            project_output_dir / "clips" / f"{clip_id}.mp4",  # Standard naming
            project_output_dir / "clips" / f"{clip_id}_clip_{clip_id}.mp4",  # Naming with clip suffix
            project_output_dir / "clips" / f"{clip_id}_clip.mp4",  # Simplified clip suffix
        ]
        
        # If clip has title, attempt title match
        if clip_title:
            # Sanitize title for filename match
            import re
            clean_title = re.sub(r'[<>:"/\\|?*]', '', clip_title)
            possible_paths.extend([
                project_output_dir / "clips" / f"{clean_title}.mp4",
                project_output_dir / "clips" / f"*{clean_title}*.mp4",
            ])
        
        logger.info(f"Searching for file, candidate paths: {[str(p) for p in possible_paths]}")
        
        # Search for video file
        video_path = None
        for path in possible_paths:
            if path.exists():
                video_path = path
                logger.info(f"Found video file: {video_path}")
                break
        
        if not video_path:
            # Fallback: scan all mp4 files in clips directory
            clips_dir = project_output_dir / "clips"
            if clips_dir.exists():
                mp4_files = list(clips_dir.glob("*.mp4"))
                logger.info(f"All mp4 files in clips directory: {[str(f) for f in mp4_files]}")
                
                # If exactly one mp4 file exists, use it
                if len(mp4_files) == 1:
                    video_path = mp4_files[0]
                    logger.info(f"Using single mp4 file: {video_path}")
                else:
                    # Try matching filename by title
                    if clip_title:
                        for mp4_file in mp4_files:
                            # Check if filename contains title keywords
                            if any(keyword in mp4_file.name for keyword in clip_title.split()[:3]):  # Use first 3 words of title
                                video_path = mp4_file
                                logger.info(f"Found match by title: {video_path}")
                                break
                    
                    # If still not found, match by clip_id
                    if not video_path:
                        for mp4_file in mp4_files:
                            if clip_id in mp4_file.name:
                                video_path = mp4_file
                                logger.info(f"Found match by clip_id: {video_path}")
                                break
        
        if not video_path:
            raise FileNotFoundError(f"Clip video file not found: {clip_id}")
        
        # Check file size
        file_size = video_path.stat().st_size
        logger.info(f"Video file size: {file_size} bytes")
        
        if file_size == 0:
            raise ValueError("Video file is empty")
        
        # Execute upload
        logger.info(f"Starting video upload: {video_path}")
        success = upload_service.upload_clip_sync(record_id_int, str(video_path))
        
        if success:
            logger.info(f"Clip upload succeeded: {clip_id}")
            upload_service.update_upload_status(record_id_int, "success")
        else:
            logger.error(f"Clip upload failed: {clip_id}")
            upload_service.update_upload_status(record_id_int, "failed", "Upload failed")
            
    except Exception as e:
        logger.error(f"Upload clip task failed: {str(e)}")
        upload_service.update_upload_status(record_id_int, "failed", str(e))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name='backend.tasks.upload.upload_project_task')
def upload_project_task(self, record_id: str, clip_ids: list):
    """Upload project task"""
    db = SessionLocal()
    try:
        logger.info(f"Starting project upload: record_id={record_id}, clip_ids={clip_ids}")
        
        # Get upload service
        upload_service = BilibiliUploadService(db)
        
        # Convert record_id to int
        try:
            record_id_int = int(record_id)
        except ValueError:
            raise ValueError(f"Invalid record_id format: {record_id}")
        
        # Get upload record
        upload_record = upload_service.get_upload_record_by_id(record_id_int)
        if not upload_record:
            raise ValueError(f"Upload record does not exist: {record_id}")
        
        # Build video file path
        project_output_dir = get_project_output_directory(str(upload_record.project_id))
        logger.info(f"Project output directory: {project_output_dir}")
        
        # Locate all clip files
        clips_dir = project_output_dir / "clips"
        if not clips_dir.exists():
            raise FileNotFoundError(f"Clips directory does not exist: {clips_dir}")
        
        # Get all mp4 files
        mp4_files = list(clips_dir.glob("*.mp4"))
        logger.info(f"Found mp4 files: {[str(f) for f in mp4_files]}")
        
        if not mp4_files:
            raise FileNotFoundError("No mp4 files found")
        
        # If single file, upload directly
        if len(mp4_files) == 1:
            video_path = mp4_files[0]
            logger.info(f"Single file upload: {video_path}")
            
            # Check file size
            file_size = video_path.stat().st_size
            if file_size == 0:
                raise ValueError("Video file is empty")
            
            # Execute upload
            success = upload_service.upload_clip(record_id_int, str(video_path))
            
            if success:
                logger.info("Project upload succeeded")
                upload_service.update_upload_status(record_id_int, "success")
            else:
                logger.error("Project upload failed")
                upload_service.update_upload_status(record_id_int, "failed", "Upload failed")
        else:
            # Multi-file upload case: merge or separate
            logger.warning(f"Found multiple video files; currently only single file upload is supported: {len(mp4_files)}")
            upload_service.update_upload_status(record_id_int, "failed", "Multi-file upload not supported yet")
            
    except Exception as e:
        logger.error(f"Upload project task failed: {str(e)}")
        upload_service.update_upload_status(record_id_int, "failed", str(e))
        raise
    finally:
        db.close()