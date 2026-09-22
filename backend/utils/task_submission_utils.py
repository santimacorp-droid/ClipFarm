"""
Task submission tool
A separate utility function, avoiding circular import issues
"""

import logging
import os
from typing import Dict, Any, Optional
from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _is_desktop_mode() -> bool:
    return os.getenv("AUTOCLIP_DESKTOP_MODE", "").lower() in {"1", "true", "yes"}


def _run_pipeline_locally(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
    """Desktop mode: Not through Redis/Celery broker, Runs the pipeline task synchronously in the background thread. 

    The desktop installer does not include Redis; the production uses core.celery_app redis://localhost. 
    Celery The task process_video_pipeline itself is「Reruns the entire pipeline synchronously within the task」
    (asyncio.run(pipeline_adapter...)), No longer dispatches sub-tasks, so can use .apply()
    Running directly in the local thread, progress is written to the Task record in the database for front-end polling. 
    """
    import uuid
    import threading

    task_id = str(uuid.uuid4())

    def run():
        try:
            # Deferred import to avoid circular dependency
            from ..tasks.processing import process_video_pipeline
            process_video_pipeline.apply(
                args=[project_id, input_video_path, input_srt_path],
                task_id=task_id,
            )
            logger.info(f"Local pipeline execution in desktop mode complete: {project_id}, task_id={task_id}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Local pipeline execution in desktop mode failed: {project_id}, Error: {e}", exc_info=True)

    threading.Thread(target=run, name=f"pipeline-{project_id[:8]}", daemon=True).start()
    logger.info(f"Desktop mode: Video pipeline is started in the local background thread {project_id}, task_id={task_id}")
    return {
        'success': True,
        'task_id': task_id,
        'status': 'PENDING',
        'message': 'Video pipeline task started locally',
    }


def submit_video_pipeline_task(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
    """
    Submit video pipeline task

    Args:
        project_id: ProjectID
        input_video_path: Input video path
        input_srt_path: Enter SRT path

    Returns:
        Task submission result
    """
    # Desktop mode without Redis uses local thread execution
    if _is_desktop_mode():
        return _run_pipeline_locally(project_id, input_video_path, input_srt_path)

    try:
        logger.info(f"Submit video pipeline task: {project_id}")
        
        # Directly use celery_app to submit tasks
        logger.info(f"Prepare to submit task to queue...")
        logger.info(f"Task name: backend.tasks.processing.process_video_pipeline")
        logger.info(f"Task parameters: {[project_id, input_video_path, input_srt_path]}")
        
        try:
            celery_task = celery_app.send_task(
                'backend.tasks.processing.process_video_pipeline',
                args=[project_id, input_video_path, input_srt_path]
            )
            
            logger.info(f"Video pipeline task submitted: {celery_task.id}")
            logger.info(f"Task status: {celery_task.state}")
            
            # Check if the task was really submitted to the queue
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            queue_length = r.llen('processing')
            logger.info(f"RedisQueue length: {queue_length}")
            
        except Exception as e:
            logger.error(f"Exception occurred during task submission: {e}")
            raise
        
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
        
        # Directly use celery_app to submit tasks
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
        logger.error(f"Failed to submit a single-step task: {project_id}, {step}, Error: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': 'Task submission failed'
        }
