"""
Task submission service
Avoid circular import issues
"""

import logging
from typing import Dict, Any, Optional
from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)

class TaskSubmissionService:
    """Task submission service"""
    
    @staticmethod
    def submit_video_pipeline_task(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        Submit video pipeline task
        
        Args:
            project_id: ProjectID
            input_video_path: Input video file path
            input_srt_path: Input SRT file path
            
        Returns:
            Task submission result
        """
        try:
            logger.info(f"Submit video pipeline task: {project_id}")
            
            # Use `celery_app` to submit tasks directly
            celery_task = celery_app.send_task(
                'tasks.processing.process_video_pipeline',
                args=[project_id, input_video_path, input_srt_path]
            )
            
            logger.info(f"Video pipeline task submitted: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': celery_task.id,
                'status': 'PENDING',
                'message': 'Video pipeline task submitted'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit video pipeline task: {project_id}, Error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Task submission failed'
            }
    
    @staticmethod
    def submit_single_step_task(project_id: str, step: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit single-step task
        
        Args:
            project_id: ProjectID
            step: Step name
            config: Processing configuration
            
        Returns:
            Task submission result
        """
        try:
            logger.info(f"Submit single-step task: {project_id}, {step}")
            
            # Use `celery_app` to submit tasks directly
            celery_task = celery_app.send_task(
                'tasks.processing.process_single_step',
                args=[project_id, step, config]
            )
            
            logger.info(f"Single-step task submitted: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': celery_task.id,
                'step': step,
                'status': 'PENDING',
                'message': f'Step {step} Task submitted'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit single-step task: {project_id}, {step}, Error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Task submission failed'
            }

