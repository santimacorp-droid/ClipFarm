"""
Local import processing task
Process video file upload: generate subtitles, thumbnails, and start processing workflow
"""

import logging
from pathlib import Path
from typing import Optional
from celery import Celery
from backend.core.database import get_db
from backend.services.project_service import ProjectService
from backend.utils.thumbnail_generator import generate_project_thumbnail
from backend.utils.task_submission_utils import submit_video_pipeline_task

logger = logging.getLogger(__name__)

# Get Celery application instance
from backend.core.celery_app import celery_app

@celery_app.task(bind=True)
def process_import_task(self, project_id: str, video_path: str, srt_file_path: Optional[str] = None):
    """
    Process asynchronous tasks for local import
    
    Args:
        project_id: projectID
        video_path: Path to video file
        srt_file_path: Subtitle file path (optional)
```)
    """
    try:
        logger.info(f"Starting processing import task: {project_id}")
        
        # Get database session
        db = next(get_db())
        project_service = ProjectService(db)
        
        # Check if a similar project is already being processed (prevent duplicate processing)
        from backend.models.task import Task, TaskStatus
        existing_task = db.query(Task).filter(
            Task.project_id == project_id,
            Task.status == TaskStatus.RUNNING,
            Task.name.like('%Import%')
        ).first()
        
        if existing_task and existing_task.celery_task_id != self.request.id:
            logger.warning(f"project {project_id} Processing task already running (task ID: {existing_task.celery_task_id}), skipping duplicate processing")
            return {
                'success': False,
                'error': 'Project currently being processed; avoid duplicate processing',
                'existing_task_id': existing_task.celery_task_id
            }
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Starting processing...'})
        
        # Step 1: Check and generate thumbnail (if not yet available)
        logger.info(f"Check project {project_id} thumbnail...")
        self.update_state(state='PROGRESS', meta={'progress': 20, 'message': 'Check thumbnail...'})
        
        project = project_service.get(project_id)
        if project and not project.thumbnail:
            logger.info(f"project {project_id} No thumbnail; begin generating...")
            self.update_state(state='PROGRESS', meta={'progress': 25, 'message': 'Generating thumbnail...'})
            
            try:
                thumbnail_data = generate_project_thumbnail(project_id, Path(video_path))
                if thumbnail_data:
                    project.thumbnail = thumbnail_data
                    db.commit()
                    logger.info(f"project {project_id} Thumbnail generated and saved successfully")
                else:
                    logger.warning(f"project {project_id} thumbnail generation failed")
            except Exception as e:
                logger.error(f"Error occurred while generating project thumbnail: {e}")
                # Thumbnail generation failure does not affect subsequent workflows
        else:
            logger.info(f"project {project_id} Thumbnail already exists; skip generation")
        
        # Step 2: Generate subtitles (if none provided)
        srt_path = srt_file_path
        if not srt_path:
            logger.info(f"Starting subtitle generation for project {project_id}...")
            self.update_state(state='PROGRESS', meta={'progress': 40, 'message': 'Generate subtitles...'})
            
            try:
                from backend.utils.speech_recognizer import generate_subtitle_for_video
                from backend.core.desktop_config import get_desktop_config
                
                # Get voice transcription settings configured by the user
                config = get_desktop_config()
                speech_config = config.speech_recognition
                
                logger.info(f"Use voice transcription configuration - method: {speech_config.method}")
                
                # Select parameters based on configuration
                if speech_config.method == "whisper_local":
                    # Use Whisper parameters configured by the user
                    model = speech_config.whisper_config.model_name
                    language = speech_config.whisper_config.language
                    enable_timestamps = speech_config.whisper_config.enable_timestamps
                    enable_punctuation = speech_config.whisper_config.enable_punctuation
                    enable_speaker_diarization = speech_config.whisper_config.enable_speaker_diarization
                    timeout = speech_config.whisper_config.timeout
                    
                    logger.info(f"Whisper config - model: {model}, language: {language}, timestamp: {enable_timestamps}")
                    
                    generated_subtitle = generate_subtitle_for_video(
                        Path(video_path),
                        language=language,
                        model=model,
                        method=speech_config.method,
                        enable_timestamps=enable_timestamps,
                        enable_punctuation=enable_punctuation,
                        enable_speaker_diarization=enable_speaker_diarization,
                        timeout=timeout
                    )
                else:
                    # Use API service
                    logger.info(f"Using API service - {speech_config.method}")
                    
                    # Retrieve API configuration based on service type
                    if speech_config.method == "openai_api":
                        api_config = speech_config.openai_config
                    elif speech_config.method == "azure_speech":
                        api_config = speech_config.azure_config
                    elif speech_config.method == "google_speech":
                        api_config = speech_config.google_config
                    elif speech_config.method == "aliyun_speech":
                        api_config = speech_config.aliyun_config
                    elif speech_config.method == "custom_api":
                        api_config = speech_config.custom_api_config
                    else:
                        raise ValueError(f"Unsupported speech recognition method: {speech_config.method}")
                    
                    generated_subtitle = generate_subtitle_for_video(
                        Path(video_path),
                        method=speech_config.method,
                        language=api_config.language,
                        api_key=api_config.api_key,
                        enable_timestamps=api_config.enable_timestamps,
                        enable_punctuation=api_config.enable_punctuation
                    )
                
                srt_path = str(generated_subtitle)
                logger.info(f"Speech transcription succeeded: {srt_path}")
                
            except Exception as e:
                logger.error(f"Speech transcription failed: {str(e)}")
                
                # If rollback mechanism is enabled, attempt to use the rollback method
                if speech_config.enable_fallback and speech_config.fallback_method != speech_config.method:
                    try:
                        logger.info(f"Attempting fallback method: {speech_config.fallback_method}")
                        
                        if speech_config.fallback_method == "whisper_local":
                            fallback_config = speech_config.whisper_config
                            generated_subtitle = generate_subtitle_for_video(
                                Path(video_path),
                                language=fallback_config.language,
                                model=fallback_config.model_name,
                                method=speech_config.fallback_method
                            )
                        else:
                            # Other fallback methods
                            generated_subtitle = generate_subtitle_for_video(
                                Path(video_path),
                                method=speech_config.fallback_method
                            )
                        
                        srt_path = str(generated_subtitle)
                        logger.info(f"Fallback method succeeded: {srt_path}")
                        
                    except Exception as fallback_error:
                        logger.error(f"Fallback method also failed: {str(fallback_error)}")
                        srt_path = None
                else:
                    srt_path = None
        
        # Step 3: Update project status to 'processing'
        logger.info(f"Updating project {project_id} status to processing...")
        self.update_state(state='PROGRESS', meta={'progress': 80, 'message': 'Starting processing pipeline...'})
        
        project_service.update_project_status(project_id, "processing")
        
        # Step 4: Start processing workflow
        from ..utils.subtitle_validator import validate_subtitle_file
        if srt_path and not validate_subtitle_file(srt_path, video_path=video_path):
            logger.warning(f"Uploaded subtitles at {srt_path} failed validation; discarding.")
            try:
                Path(srt_path).unlink(missing_ok=True)
            except Exception:
                pass
            srt_path = None

        if not srt_path:
            # Check if an old corrupted/placeholder input.srt exists in raw_dir
            raw_srt = Path(video_path).parent / "input.srt"
            if raw_srt.exists() and not validate_subtitle_file(raw_srt, video_path=video_path):
                logger.info(f"Removing invalid placeholder file: {raw_srt}")
                try:
                    raw_srt.unlink(missing_ok=True)
                except Exception:
                    pass
            srt_path = None
            logger.info("No subtitles provided; pipeline will automatically transcribe video using AI Whisper")

        try:
            task_result = submit_video_pipeline_task(
                project_id=project_id,
                input_video_path=video_path,
                input_srt_path=srt_path
            )
            
            if task_result['success']:
                logger.info(f"project {project_id} Task started, Celery taskID: {task_result['task_id']}")
                self.update_state(state='PROGRESS', meta={'progress': 100, 'message': 'Processing pipeline started'})
            else:
                logger.error(f"Celery task submission failed: {task_result['error']}")
                project_service.update_project_status(project_id, "failed")
                self.update_state(state='FAILURE', meta={'error': task_result['error']})
                return
                
        except Exception as e:
            logger.error(f"Start project {project_id} Processing failed: {str(e)}")
            project_service.update_project_status(project_id, "failed")
            self.update_state(state='FAILURE', meta={'error': str(e)})
            return
        
        logger.info(f"Import task completed: {project_id}")
        return {
            'status': 'completed',
            'project_id': project_id,
            'message': 'Import processing completed'
        }
        
    except Exception as e:
        logger.error(f"Import task failed: {project_id}, Error: {e}")
        
        # Update project status to 'failed'
        try:
            db = next(get_db())
            project_service = ProjectService(db)
            project_service.update_project_status(project_id, "failed")
        except:
            pass
        
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        try:
            db.close()
        except:
            pass

