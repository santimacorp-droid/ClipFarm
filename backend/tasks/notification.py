"""
Notification task
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from celery import shared_task
from ..core.celery_app import celery_app
from datetime import datetime
from ..core.database import SessionLocal
from ..models.task import Task, TaskStatus
from ..services.websocket_notification_service import WebSocketNotificationService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='backend.tasks.notification.send_processing_notification')
def send_processing_notification(self, project_id: str, task_id: str, message: str, notification_type: str = 'info') -> Dict[str, Any]:
    """
    Sending processing notification
    
    Args:
        project_id: ProjectID
        task_id: TaskID
        message: Notification message
        notification_type: Notification type (info, warning, error, success)
        
    Returns:
        Notification result
    """
    logger.info(f"Sending processing notification: {project_id}, {task_id}, {notification_type}")
    
    try:
        # Creating database session
        db = SessionLocal()
        
        try:
            # Here you can integrate an actual notification system.
            # For example: WebSocket, email, SMS, etc.
            
            # Simulating notification sending
            notification_data = {
                'project_id': project_id,
                'task_id': task_id,
                'message': message,
                'type': notification_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Notification sent: {notification_data}")
            
            return {
                'success': True,
                'project_id': project_id,
                'task_id': task_id,
                'notification': notification_data,
                'message': 'Notification sent successfully'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Notification sent failed: {project_id}, {task_id}, Error: {e}")
        raise


@shared_task(bind=True, name='backend.tasks.notification.send_error_notification')
def send_error_notification(self, project_id: str, task_id: str, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Sending error notification
    
    Args:
        project_id: ProjectID
        task_id: TaskID
        error_message: Error message
        error_details: Error details
        
    Returns:
        Notification result
    """
    logger.error(f"Sending error notification: {project_id}, {task_id}, {error_message}")
    
    try:
        # Creating database session
        db = SessionLocal()
        
        try:
            # Updating task status
            # task_repo = TaskRepository(db) # This line was removed as per the new_code
            # task = task_repo.get_by_id(task_id) # This line was removed as per the new_code
            # if task: # This line was removed as per the new_code
            #     task.status = TaskStatus.FAILED # This line was removed as per the new_code
            #     task.error_message = error_message # This line was removed as per the new_code
            #     db.commit() # This line was removed as per the new_code
            
            # Sending error notification
            notification_data = {
                'project_id': project_id,
                'task_id': task_id,
                'type': 'error',
                'message': error_message,
                'details': error_details,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.error(f"Error notification sent: {notification_data}")
            
            return {
                'success': True,
                'project_id': project_id,
                'task_id': task_id,
                'notification': notification_data,
                'message': 'Successfully sent error notification'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to send error notification: {project_id}, {task_id}, Error: {e}")
        raise


@shared_task(bind=True, name='backend.tasks.notification.send_completion_notification')
def send_completion_notification(self, project_id: str, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sending completion notification
    
    Args:
        project_id: ProjectID
        task_id: TaskID
        result: Processing result
        
    Returns:
        Notification result
    """
    logger.info(f"Sending completion notification: {project_id}, {task_id}")
    
    try:
        # Creating database session
        db = SessionLocal()
        
        try:
            # Updating task status
            # task_repo = TaskRepository(db) # This line was removed as per the new_code
            # task = task_repo.get_by_id(task_id) # This line was removed as per the new_code
            # if task: # This line was removed as per the new_code
            #     task.status = TaskStatus.COMPLETED # This line was removed as per the new_code
            #     task.result = result # This line was removed as per the new_code
            #     db.commit() # This line was removed as per the new_code
            
            # Sending completion notification
            notification_data = {
                'project_id': project_id,
                'task_id': task_id,
                'type': 'success',
                'message': 'Processing complete',
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Completion notification sent: {notification_data}")
            
            return {
                'success': True,
                'project_id': project_id,
                'task_id': task_id,
                'notification': notification_data,
                'message': 'Successfully sent completion notification'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to send completion notification: {project_id}, {task_id}, Error: {e}")
        raise