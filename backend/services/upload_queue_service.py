import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

from sqlalchemy.orm import Session
from celery import Celery

from ..core.database import get_db
from ..models.bilibili import BilibiliAccount, BilibiliUploadRecord
from ..services.bilibili_service import BilibiliAccountService, BilibiliUploadService
from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

class UploadTask:
    """Upload Task Class"""
    def __init__(self, task_id: str, video_path: str, title: str, 
                 description: str = "", tags: str = "", 
                 account_id: Optional[int] = None, priority: TaskPriority = TaskPriority.NORMAL):
        self.task_id = task_id
        self.video_path = video_path
        self.title = title
        self.description = description
        self.tags = tags
        self.account_id = account_id
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.progress = 0
        self.error_message = None
        self.retry_count = 0
        self.max_retries = 3
        self.celery_task_id = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "video_path": self.video_path,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "account_id": self.account_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "celery_task_id": self.celery_task_id
        }

class UploadQueueService:
    """Upload queue management service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.bilibili_account_service = BilibiliAccountService(db)
        self.bilibili_upload_service = BilibiliUploadService(db)
        self.task_queue: Dict[str, UploadTask] = {}
        self.processing_tasks: Dict[str, UploadTask] = {}
        self.max_concurrent_uploads = 3  # Maximum concurrent uploads limit reached
        
    def add_task(self, video_path: str, title: str, description: str = "", 
                 tags: str = "", account_id: Optional[int] = None, 
                 priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Adding upload task"""
        try:
            task_id = str(uuid4())
            task = UploadTask(
                task_id=task_id,
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                account_id=account_id,
                priority=priority
            )
            
            # Validating video file
            import os
            if not os.path.exists(video_path):
                raise ValueError(f"Video file does not exist: {video_path}")
            
            # If no account is specified, automatically select the best account
            if not account_id:
                best_account = self.bilibili_account_service.select_best_account()
                if not best_account:
                    raise ValueError("No available Bilibili accounts")
                task.account_id = best_account.id
            
            self.task_queue[task_id] = task
            task.status = TaskStatus.QUEUED
            
            logger.info(f"Adding upload task: {task_id} - {title}")
            
            # Attempt immediate task processing
            asyncio.create_task(self._process_queue())
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to add upload task: {e}")
            raise
    
    def add_batch_tasks(self, tasks_data: List[Dict[str, Any]]) -> List[str]:
        """Batch add upload tasks"""
        try:
            task_ids = []
            
            # Account assignment for batch tasks
            accounts = self.bilibili_account_service.rotate_accounts_for_batch_upload(len(tasks_data))
            
            for i, task_data in enumerate(tasks_data):
                # Assign account
                if i < len(accounts):
                    task_data['account_id'] = accounts[i].id
                
                task_id = self.add_task(**task_data)
                task_ids.append(task_id)
            
            logger.info(f"Batch add {len(task_ids)} upload tasks")
            return task_ids
            
        except Exception as e:
            logger.error(f"Batch add upload task failed: {e}")
            raise
    
    async def _process_queue(self):
        """Processing task queue"""
        try:
            # Check if there are idle processing slots
            if len(self.processing_tasks) >= self.max_concurrent_uploads:
                return
            
            # Get unprocessed tasks (sorted by priority)
            pending_tasks = [
                task for task in self.task_queue.values() 
                if task.status == TaskStatus.QUEUED
            ]
            
            if not pending_tasks:
                return
            
            # Sort by priority and creation time
            pending_tasks.sort(key=lambda t: (-t.priority.value, t.created_at))
            
            # Process task
            available_slots = self.max_concurrent_uploads - len(self.processing_tasks)
            for task in pending_tasks[:available_slots]:
                await self._start_task(task)
                
        except Exception as e:
            logger.error(f"Task queue processing failed: {e}")
    
    async def _start_task(self, task: UploadTask):
        """Starting individual task"""
        try:
            task.status = TaskStatus.PROCESSING
            task.updated_at = datetime.now()
            
            # Moving to processing queue
            self.processing_tasks[task.task_id] = task
            if task.task_id in self.task_queue:
                del self.task_queue[task.task_id]
            
            logger.info(f"Start uploading task: {task.task_id}")
            
            # Submit to Celery
            celery_task = upload_video_task.delay(
                task.task_id,
                task.video_path,
                task.title,
                task.description,
                task.tags,
                task.account_id
            )
            
            task.celery_task_id = celery_task.id
            
        except Exception as e:
            logger.error(f"Failed to start task: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            self._move_task_to_completed(task)
    
    def _move_task_to_completed(self, task: UploadTask):
        """Move task to completed state"""
        task.updated_at = datetime.now()
        
        # Removing from processing queue
        if task.task_id in self.processing_tasks:
            del self.processing_tasks[task.task_id]
        
        # Continue processing other tasks in the queue
        asyncio.create_task(self._process_queue())
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Failed to get task status"""
        try:
            # First look in the processing queue
            if task_id in self.processing_tasks:
                task = self.processing_tasks[task_id]
                
                # Check Celery task status
                if task.celery_task_id:
                    celery_task = celery_app.AsyncResult(task.celery_task_id)
                    if celery_task.state == 'SUCCESS':
                        task.status = TaskStatus.COMPLETED
                        task.progress = 100
                        self._move_task_to_completed(task)
                    elif celery_task.state == 'FAILURE':
                        task.status = TaskStatus.FAILED
                        task.error_message = str(celery_task.info)
                        self._move_task_to_completed(task)
                    elif celery_task.state == 'PENDING':
                        task.progress = 0
                    elif celery_task.state == 'PROGRESS':
                        if hasattr(celery_task.info, 'get'):
                            task.progress = celery_task.info.get('progress', 0)
                
                return task.to_dict()
            
            # Looking up in waiting queue
            if task_id in self.task_queue:
                return self.task_queue[task_id].to_dict()
            
            # Look up completed tasks in database
            upload_record = self.db.query(BilibiliUploadRecord).filter(
                BilibiliUploadRecord.task_id == task_id
            ).first()
            
            if upload_record:
                return {
                    "task_id": task_id,
                    "status": upload_record.status,
                    "progress": 100 if upload_record.status == "completed" else 0,
                    "bv_id": upload_record.bv_id,
                    "error_message": upload_record.error_message,
                    "created_at": upload_record.created_at.isoformat(),
                    "updated_at": upload_record.updated_at.isoformat() if upload_record.updated_at else None
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel task"""
        try:
            # Cancel in waiting queue
            if task_id in self.task_queue:
                task = self.task_queue[task_id]
                task.status = TaskStatus.CANCELLED
                del self.task_queue[task_id]
                logger.info(f"Cancel pending task: {task_id}")
                return True
            
            # Canceling task in queue
            if task_id in self.processing_tasks:
                task = self.processing_tasks[task_id]
                
                # Cancel Celery task
                if task.celery_task_id:
                    celery_app.control.revoke(task.celery_task_id, terminate=True)
                
                task.status = TaskStatus.CANCELLED
                self._move_task_to_completed(task)
                logger.info(f"Cancelling task currently being processed: {task_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Canceling task failed: {e}")
            return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Failed to get queue status"""
        try:
            queued_count = len([t for t in self.task_queue.values() if t.status == TaskStatus.QUEUED])
            processing_count = len(self.processing_tasks)
            
            return {
                "queued_tasks": queued_count,
                "processing_tasks": processing_count,
                "max_concurrent": self.max_concurrent_uploads,
                "queue_details": [
                    {
                        "task_id": task.task_id,
                        "title": task.title,
                        "priority": task.priority.value,
                        "created_at": task.created_at.isoformat()
                    }
                    for task in sorted(self.task_queue.values(), key=lambda t: (-t.priority.value, t.created_at))
                ],
                "processing_details": [
                    {
                        "task_id": task.task_id,
                        "title": task.title,
                        "progress": task.progress,
                        "account_id": task.account_id
                    }
                    for task in self.processing_tasks.values()
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {"error": str(e)}

# Celery task definition
@celery_app.task(bind=True)
def upload_video_task(self, task_id: str, video_path: str, title: str, 
                     description: str, tags: str, account_id: int):
    """CeleryUpload task"""
    try:
        # Updating task progress
        self.update_state(state='PROGRESS', meta={'progress': 10})
        
        # Error occurred while getting database session
        db = next(get_db())
        bilibili_upload_service = BilibiliUploadService(db)
        bilibili_account_service = BilibiliAccountService(db)
        
        # Preparing upload data
        clip_data = {
            'video_path': video_path,
            'title': title,
            'description': description,
            'tags': tags
        }
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 30})
        
        # Upload execution - use thread pool to avoid event loop conflict
        import concurrent.futures
        
        def run_async_upload():
            return asyncio.run(
                bilibili_upload_service.upload_clip(clip_data, account_id)
            )
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_async_upload)
            upload_record = future.result()
        
        # Updating task ID
        upload_record.task_id = task_id
        db.commit()
        
        # Update account usage time
        bilibili_account_service.update_account_usage(account_id)
        
        if upload_record.status == 'completed':
            self.update_state(state='PROGRESS', meta={'progress': 100})
            return {
                'status': 'completed',
                'bv_id': upload_record.bv_id,
                'upload_record_id': upload_record.id
            }
        else:
            raise Exception(upload_record.error_message or "Upload failed")
            
    except Exception as e:
        logger.error(f"CeleryUpload task failed: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)