"""
Task managementAPIRoute
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.models.task import Task
from backend.schemas.task import TaskResponse, TaskCreate, TaskUpdate
from backend.services.task_service import TaskService
from backend.services.task_queue_service import TaskQueueService

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_task_config_value(task, key: str, default=None):
    config = task.task_config or {}
    return config.get(key, default)

@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Getting task list"""
    try:
        task_service = TaskService(db)
        tasks = task_service.get_tasks(
            skip=skip,
            limit=limit,
            status=status,
            project_id=project_id
        )
        return tasks
    except Exception as e:
        logger.exception("Failed to retrieve task list")
        raise HTTPException(status_code=500, detail="Failed to retrieve task list. Please try again later")

@router.get("/project/{project_id}", response_model=List[TaskResponse])
async def get_project_tasks(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Get task list for specified project"""
    try:
        task_service = TaskService(db)
        tasks = task_service.get_tasks_by_project_id(project_id)
        return tasks
    except Exception as e:
        logger.exception("Failed to retrieve project tasks: %s", project_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve project tasks. Please try again later")

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve single task details"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task does not exist")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retrieve task details: %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve task details. Please try again later")

@router.post("/", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db)
):
    """Create new task"""
    try:
        task_service = TaskService(db)
        task = task_service.create_task(task_data)
        return task
    except Exception as e:
        logger.exception("Failed to create task")
        raise HTTPException(status_code=500, detail="Failed to create task. Please try again later")

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    db: Session = Depends(get_db)
):
    """Updating task"""
    try:
        task_service = TaskService(db)
        task = task_service.update_task(task_id, task_data)
        if not task:
            raise HTTPException(status_code=404, detail="Task does not exist")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update task: %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to update task. Please try again later")

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Deleting task"""
    try:
        task_service = TaskService(db)
        success = task_service.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="Task does not exist")
        return {"message": "Task deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete task: %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to delete task. Please try again later")

@router.post("/{task_id}/submit")
async def submit_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Submit task to queue"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task does not exist")
        
        queue_service = TaskQueueService(db)
        task_type = str(task.task_type.value if hasattr(task.task_type, "value") else task.task_type)

        if task_type == "video_processing":
            input_video_path = _get_task_config_value(task, "input_video_path")
            input_srt_path = _get_task_config_value(task, "input_srt_path")
            if not input_video_path:
                raise HTTPException(status_code=400, detail="Task missing input_video_path Configuration")
            result = queue_service.submit_video_processing_task(
                project_id=task.project_id,
                input_video_path=input_video_path,
                input_srt_path=input_srt_path,
            )
        elif task_type == "clip_generation":
            clip_data = _get_task_config_value(task, "clip_data", [])
            result = queue_service.submit_video_clips_task(task.project_id, clip_data)
        elif task_type == "collection_creation":
            collection_data = _get_task_config_value(task, "collection_data", [])
            result = queue_service.submit_collection_generation_task(task.project_id, collection_data)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported task type: {task_type}")
        
        return {
            "message": "Task submitted to queue",
            "task_id": task_id,
            "queue_task_id": result.get("task_id"),
            "celery_task_id": result.get("celery_task_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to submit task: %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to submit task. Please try again later")

@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Retry failed task"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task does not exist")
        
        # Reset task status and resubmit
        task_service.update_task(task_id, TaskUpdate(status="pending", progress=0))
        
        queue_service = TaskQueueService(db)
        task_type = str(task.task_type.value if hasattr(task.task_type, "value") else task.task_type)

        if task_type == "video_processing":
            input_video_path = _get_task_config_value(task, "input_video_path")
            input_srt_path = _get_task_config_value(task, "input_srt_path")
            if not input_video_path:
                raise HTTPException(status_code=400, detail="Task missing input_video_path Configuration")
            result = queue_service.submit_video_processing_task(
                project_id=task.project_id,
                input_video_path=input_video_path,
                input_srt_path=input_srt_path,
            )
        elif task_type == "clip_generation":
            clip_data = _get_task_config_value(task, "clip_data", [])
            result = queue_service.submit_video_clips_task(task.project_id, clip_data)
        elif task_type == "collection_creation":
            collection_data = _get_task_config_value(task, "collection_data", [])
            result = queue_service.submit_collection_generation_task(task.project_id, collection_data)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported task type: {task_type}")
        
        return {
            "message": "Task has been resent",
            "task_id": task_id,
            "queue_task_id": result.get("task_id"),
            "celery_task_id": result.get("celery_task_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retry task: %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to retry task. Please try again later")

@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Getting task status"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task does not exist")
        
        return {
            "task_id": task_id,
            "status": task.status,
            "progress": task.progress,
            "message": task.name,
            "error": task.error_message,
            "updated_at": task.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retrieve task status: %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve task status. Please try again later")

