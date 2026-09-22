"""
Task progress update service
Provide real-time progress update feature
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ..core.database import SessionLocal
from ..models.task import Task, TaskStatus
from ..core.websocket_manager import manager as websocket_manager

logger = logging.getLogger(__name__)

class ProgressUpdateService:
    """Task progress update service"""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
    
    async def update_task_progress(
        self, 
        task_id: str, 
        progress: float, 
        current_step: str = None,
        step_details: str = None
    ):
        """Update task progress"""
        try:
            # Update task progress in database
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.progress = progress
                    if current_step:
                        task.current_step = current_step
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    
                    # Log to active tasks
                    self.active_tasks[task_id] = {
                        'progress': progress,
                        'current_step': current_step,
                        'step_details': step_details,
                        'updated_at': datetime.utcnow()
                    }
                    
                    logger.info(f"Task {task_id} Progress updated: {progress}% - {current_step}")
                    
                    # Send progress update via WebSocket
                    await self.broadcast_progress_update(task)
                else:
                    logger.warning(f"Task {task_id} Does not exist")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to update task progress: {e}")
    
    async def broadcast_progress_update(self, task: Task):
        """Broadcast progress update to frontend"""
        try:
            # Build progress update message
            progress_message = {
                'type': 'task_progress_update',
                'task_id': task.id,
                'project_id': task.project_id,
                'progress': task.progress,
                'current_step': task.current_step,
                'status': task.status,
                'updated_at': task.updated_at.isoformat() if task.updated_at else None
            }
            
            # Send to all connected clients
            await websocket_manager.broadcast(progress_message)
            logger.debug(f"Progress update broadcasted: {progress_message}")
            
        except Exception as e:
            logger.error(f"Broadcast progress update failed: {e}")
    
    async def start_progress_monitoring(self, task_id: str):
        """Start monitoring task progress"""
        try:
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    # Mark task as running
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.utcnow()
                    db.commit()
                    
                    # Add to active tasks list
                    self.active_tasks[task_id] = {
                        'progress': 0.0,
                        'current_step': 'Initialized',
                        'step_details': 'Start processing task',
                        'started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                    
                    logger.info(f"Start monitoring task progress: {task_id}")
                    
                    # Send task start notification
                    await self.broadcast_progress_update(task)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Starting progress monitoring failed: {e}")
    
    async def complete_task(self, task_id: str, result: Dict[str, Any] = None, error: str = None):
        """Task completed"""
        try:
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    if error:
                        task.status = TaskStatus.FAILED
                        task.error_message = error
                    else:
                        task.status = TaskStatus.COMPLETED
                        task.progress = 100.0
                        task.current_step = 'Done'
                    
                    task.completed_at = datetime.utcnow()
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    
                    # Remove from active tasks list
                    if task_id in self.active_tasks:
                        del self.active_tasks[task_id]
                    
                    logger.info(f"Task completed: {task_id}, Status: {task.status}")
                    
                    # Send task completion notification
                    await self.broadcast_progress_update(task)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Completing task failed: {e}")
    
    def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task progress"""
        return self.active_tasks.get(task_id)
    
    def get_all_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all active tasks"""
        return self.active_tasks.copy()

# Global instance
progress_update_service = ProgressUpdateService()
