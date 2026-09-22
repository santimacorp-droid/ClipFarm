"""
Task queue management service
Manages the submission, monitoring, and status querying of Celery tasks
"""

import logging
from typing import Dict, Any, Optional, List
from celery.result import AsyncResult
from sqlalchemy.orm import Session

from ..core.celery_app import celery_app
from ..core.database import SessionLocal
from ..models.task import Task, TaskStatus, TaskType
from ..repositories.task_repository import TaskRepository
from ..tasks.processing import process_video_pipeline, process_single_step, retry_processing_step
from ..tasks.video import extract_video_clips, generate_video_collections, optimize_video_quality
from ..tasks.notification import send_processing_notification, send_error_notification, send_completion_notification
from ..tasks.maintenance import cleanup_expired_tasks, health_check, backup_project_data

logger = logging.getLogger(__name__)


class TaskQueueService:
    """Task queue management service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)
    
    def submit_video_processing_task(
        self,
        project_id: str,
        input_video_path: str,
        input_srt_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit video processing task
        
        Args:
            project_id: ProjectID
            input_video_path: Enter video path
            input_srt_path: Enter SRT path
            
        Returns:
            Submission result
        """
        logger.info(f"Submit video processing task: {project_id}")
        
        try:
            # Create and save task record
            task = self.task_repo.create(
                project_id=project_id,
                name="Video pipeline processing",
                description=f"Process project {project_id} of the video pipeline",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=1
            )
            
            # Submit Celery task
            celery_task = process_video_pipeline.delay(
                project_id=project_id,
                input_video_path=input_video_path,
                input_srt_path=input_srt_path,
            )
            
            # Update task record
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"Video processing task submitted: {task.id}, CeleryTaskID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'status': 'PENDING',
                'message': 'Video processing task submitted'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit video processing task: {project_id}, Error: {e}")
            raise
    
    def submit_single_step_task(
        self,
        project_id: str,
        step_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit individual step processing task
        
        Args:
            project_id: ProjectID
            step_name: Step name
            config: Step configuration parameters
            
        Returns:
            Submission result
        """
        logger.info(f"Submit individual step task: {project_id}, {step_name}")
        
        try:
            # Create and save task record
            task = self.task_repo.create(
                project_id=project_id,
                name=f"Step processing: {step_name}",
                description=f"Process project {project_id} steps {step_name}",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=2
            )
            
            # Submit Celery task
            celery_task = process_single_step.delay(project_id, step_name, config or {})
            
            # Update task record
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"Individual step task submitted: {task.id}, CeleryTaskID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'step': step_name,
                'status': 'PENDING',
                'message': f'Step {step_name} Processing task submitted'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit individual step task: {project_id}, {step_name}, Error: {e}")
            raise
    
    def submit_retry_task(
        self,
        project_id: str,
        task_id: str,
        step_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit retry task
        
        Args:
            project_id: ProjectID
            task_id: TaskID
            step_name: Step name
            config: Step configuration parameters
            
        Returns:
            Submission result
        """
        logger.info(f"Submit retry task: {project_id}, {task_id}, {step_name}")
        
        try:
            # Create and save task record
            task = self.task_repo.create(
                project_id=project_id,
                name=f"Retry step: {step_name}",
                description=f"Retry project {project_id} steps {step_name}",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=3
            )
            
            # Submit Celery task
            celery_task = retry_processing_step.delay(project_id, step_name, config or {}, task_id)
            
            # Update task record
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"Retrying task submitted: {task.id}, CeleryTaskID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'original_task_id': task_id,
                'step': step_name,
                'status': 'PENDING',
                'message': f'Step {step_name} Retrying task submitted'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit retry task: {project_id}, {task_id}, {step_name}, Error: {e}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status
        
        Args:
            task_id: TaskID
            
        Returns:
            Task status information
        """
        try:
            # Get database task record
            task = self.task_repo.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}
            
            # Get Celery task status
            celery_status = {}
            if task.celery_task_id:
                celery_result = AsyncResult(task.celery_task_id, app=celery_app)
                celery_status = {
                    'celery_task_id': task.celery_task_id,
                    'celery_status': celery_result.status,
                    'celery_result': celery_result.result if celery_result.ready() else None,
                    'celery_info': celery_result.info if hasattr(celery_result, 'info') else None
                }
            
            return {
                'task_id': task.id,
                'project_id': task.project_id,
                'name': task.name,
                'status': task.status.value,
                'task_type': task.task_type.value,
                'progress': task.progress,
                'error_message': task.error_message,
                'result': task.result_data,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat(),
                'celery_status': celery_status
            }
            
        except Exception as e:
            logger.error(f"Failed to get task status: {task_id}, Error: {e}")
            return {'error': f'Failed to get task status: {e}'}
    
    def get_project_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all project tasks
        
        Args:
            project_id: ProjectID
            
        Returns:
            Task list
        """
        try:
            tasks = self.task_repo.get_by_project(project_id)
            return [
                {
                    'task_id': task.id,
                    'name': task.name,
                    'status': task.status.value,
                    'task_type': task.task_type.value,
                    'progress': task.progress,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': task.updated_at.isoformat()
                }
                for task in tasks
            ]
            
        except Exception as e:
            logger.error(f"Failed to get project tasks: {project_id}, Error: {e}")
            return []
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        Cancel task
        
        Args:
            task_id: TaskID
            
        Returns:
            Cancel result
        """
        try:
            task = self.task_repo.get_by_id(task_id)
            if not task:
                return {'error': 'Task not found'}
            
            # Cancel Celery task
            if task.celery_task_id:
                celery_result = AsyncResult(task.celery_task_id, app=celery_app)
                celery_result.revoke(terminate=True)
            
            # Update task status
            task.status = TaskStatus.CANCELLED
            self.db.commit()
            
            logger.info(f"Task cancelled: {task_id}")
            return {
                'success': True,
                'task_id': task_id,
                'status': 'CANCELLED',
                'message': 'Task cancelled'
            }
            
        except Exception as e:
            logger.error(f"Canceling task failed: {task_id}, Error: {e}")
            return {'error': f'Canceling task failed: {e}'}
    
    def submit_video_clips_task(self, project_id: str, clip_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Submit video clip extraction task
        
        Args:
            project_id: ProjectID
            clip_data: Fragment data
            
        Returns:
            Submission result
        """
        logger.info(f"Submit video clip extraction task: {project_id}")
        
        try:
            # Create and save task record
            task = self.task_repo.create(
                project_id=project_id,
                name="Extract video segments",
                description=f"Extract project {project_id} Video segment",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=2
            )
            
            # Submit Celery task
            celery_task = extract_video_clips.delay(project_id, clip_data)
            
            # Update task record
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"Video clip extraction task submitted: {task.id}, CeleryTaskID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'clip_count': len(clip_data),
                'status': 'PENDING',
                'message': f'Video clip extraction task submitted, total: {count} {len(clip_data)} fragments'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit video clip extraction task: {project_id}, Error: {e}")
            raise
    
    def submit_collection_generation_task(self, project_id: str, collection_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Submit playlist generation task
        
        Args:
            project_id: ProjectID
            collection_data: Collection data
            
        Returns:
            Submission result
        """
        logger.info(f"Submit playlist generation task: {project_id}")
        
        try:
            # Create and save task record
            task = self.task_repo.create(
                project_id=project_id,
                name="Video collection generated",
                description=f"Generate project {project_id} Video collection",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=2
            )
            
            # Submit Celery task
            celery_task = generate_video_collections.delay(project_id, collection_data)
            
            # Update task record
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"Playlist generation task submitted: {task.id}, CeleryTaskID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'collection_count': len(collection_data),
                'status': 'PENDING',
                'message': f'Video playlist generation task submitted, total: {count} {len(collection_data)} collections'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit playlist generation task: {project_id}, Error: {e}")
            raise 