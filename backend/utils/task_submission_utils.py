"""
Task submission tool
A separate utility function, avoiding circular import issues
"""

import logging
import os
from typing import Dict, Any, Optional
from ..core.celery_app import celery_app, should_run_locally, _LOCAL_TASK_EXECUTOR

logger = logging.getLogger(__name__)


def _is_desktop_mode() -> bool:
    return should_run_locally()


def _run_pipeline_locally(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
    """Runs the pipeline task in a bounded local worker pool without requiring Redis."""
    import uuid

    task_id = str(uuid.uuid4())

    def run():
        try:
            from ..tasks.processing import process_video_pipeline
            process_video_pipeline.apply(
                args=[project_id, input_video_path, input_srt_path],
                task_id=task_id,
            )
            logger.info(f"Local pipeline execution complete: {project_id}, task_id={task_id}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Local pipeline execution failed: {project_id}, Error: {e}", exc_info=True)

    _LOCAL_TASK_EXECUTOR.submit(run)
    logger.info(f"Video pipeline queued in local task executor: {project_id}, task_id={task_id}")
    return {
        'success': True,
        'task_id': task_id,
        'status': 'PENDING',
        'message': 'Video pipeline task started locally',
    }


def submit_video_pipeline_task(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
    """Submit video pipeline task, automatically falling back to local thread if Redis is unavailable."""
    if should_run_locally():
        return _run_pipeline_locally(project_id, input_video_path, input_srt_path)

    try:
        logger.info(f"Submit video pipeline task to Celery queue: {project_id}")
        celery_task = celery_app.send_task(
            'backend.tasks.processing.process_video_pipeline',
            args=[project_id, input_video_path, input_srt_path]
        )
        logger.info(f"Video pipeline task submitted to Celery: {celery_task.id}")
        return {
            'success': True,
            'task_id': celery_task.id,
            'status': 'PENDING',
            'message': 'Video pipeline task submitted'
        }
    except Exception as e:
        logger.warning(
            f"Celery queue submission failed ({e}); falling back to local in-process thread for project {project_id}"
        )
        return _run_pipeline_locally(project_id, input_video_path, input_srt_path)

def submit_single_step_task(project_id: str, step: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Submit single-step task, automatically falling back to local thread if Redis is unavailable."""
    import uuid
    import threading

    task_id = str(uuid.uuid4())

    def _run_single_step_locally():
        def run():
            try:
                from ..tasks.processing import process_single_step
                process_single_step.apply(
                    args=[project_id, step, config],
                    task_id=task_id,
                )
                logger.info(f"Local single-step task complete: {project_id}, step={step}, task_id={task_id}")
            except Exception as e:
                logger.error(f"Local single-step execution failed: {project_id}, Error: {e}", exc_info=True)

        _LOCAL_TASK_EXECUTOR.submit(run)
        return {
            'success': True,
            'task_id': task_id,
            'step': step,
            'status': 'PENDING',
            'message': f'Step {step} task started locally'
        }

    if should_run_locally():
        return _run_single_step_locally()

    try:
        logger.info(f"Submit single-step task to Celery: {project_id}, {step}")
        celery_task = celery_app.send_task(
            'tasks.processing.process_single_step',
            args=[project_id, step, config]
        )
        return {
            'success': True,
            'task_id': celery_task.id,
            'step': step,
            'status': 'PENDING',
            'message': f'Step {step} Task submitted'
        }
    except Exception as e:
        logger.warning(
            f"Celery queue submission failed ({e}); falling back to local in-process thread for step {step}"
        )
        return _run_single_step_locally()
