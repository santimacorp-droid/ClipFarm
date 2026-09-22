"""
WebSocketNotification service
Provide real-time notification functionality
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..core.websocket_manager import manager, WebSocketMessage

logger = logging.getLogger(__name__)

class WebSocketNotificationService:
    """WebSocketNotification service"""
    
    @staticmethod
    async def send_task_update(task_id: str, status: str, progress: Optional[int] = None,
                              message: Optional[str] = None, error: Optional[str] = None):
        """Send task update notification"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status=status,
                progress=progress,
                message=message,
                error=error
            )
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            
            # Sending notifications to subscribers of a specific task topic
            topic = f"task_{task_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"Task update notification sent: {task_id} - {status}")
            
        except Exception as e:
            logger.error(f"Failed to send task update notification: {e}")
    
    @staticmethod
    async def send_project_update(project_id: str, status: str, progress: Optional[int] = None,
                                message: Optional[str] = None):
        """Send project update notification"""
        try:
            notification = WebSocketMessage.create_project_update(
                project_id=project_id,
                status=status,
                progress=progress,
                message=message
            )
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            
            # Sending notifications to subscribers of a specific project topic
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"Project update notification sent: {project_id} - {status}")
            
        except Exception as e:
            logger.error(f"Failed to send project update notification: {e}")
    
    @staticmethod
    async def send_system_notification(notification_type: str, title: str, message: str,
                                     level: str = "info"):
        """Sending system notification"""
        try:
            notification = WebSocketMessage.create_system_notification(
                notification_type=notification_type,
                title=title,
                message=message,
                level=level
            )
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            
            logger.info(f"System notification successfully sent: {title} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to send system notification: {e}")
    
    @staticmethod
    async def send_error_notification(error_type: str, error_message: str,
                                    details: Optional[Dict[str, Any]] = None):
        """Sending error notification"""
        try:
            notification = WebSocketMessage.create_error_notification(
                error_type=error_type,
                error_message=error_message,
                details=details
            )
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            
            logger.error(f"Error notification already sent: {error_type} - {error_message}")
            
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
    
    @staticmethod
    async def send_processing_start(project_id: str, task_id: str):
        """Send processing started notification"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status="running",
                progress=0,
                message="Initiating project processing"
            )
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            
            # Sending notifications to subscribers of a specific project topic
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"Processing started notification sent: {project_id} - {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to send processing started notification: {e}")
    
    @staticmethod
    async def send_processing_progress(project_id: str, task_id: str, progress: int, message: str, 
                                     current_step: int = 0, total_steps: int = 6, step_name: str = ""):
        """Preparing to send processing progress notification"""
        try:
            # Creating enhanced progress update message
            notification = {
                'type': 'task_progress_update',
                'task_id': task_id,
                'project_id': project_id,
                'status': 'running',
                'progress': progress,
                'current_step': current_step,
                'total_steps': total_steps,
                'step_name': step_name,
                'message': message,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Sending progress notification: {notification}")
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            logger.info(f"Broadcasted progress notification to all users: {notification}")
            
            # Sending notifications to subscribers of a specific project topic
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            logger.info(f"Sent progress notification to topic {topic} subscriber(s): {notification}")
            
            logger.info(f"Processing progress notification sent: {project_id} - {task_id} - {progress}% - {step_name}")
            
        except Exception as e:
            logger.error(f"Failed to send processing progress notification: {e}")
            import traceback
            logger.error(f"Error details: {traceback.format_exc()}")
    
    @staticmethod
    async def send_processing_complete(project_id: str, task_id: str, result: dict):
        """Send processing completion notification"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status="completed",
                progress=100,
                message="Project processing complete"
            )
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            
            # Sending notifications to subscribers of a specific project topic
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"Processing completion notification sent: {project_id} - {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to send processing completion notification: {e}")
    
    @staticmethod
    async def send_processing_error(project_id: str, task_id: str, error_message: str):
        """Send processing error notification"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status="failed",
                progress=0,
                error=error_message
            )
            
            # Broadcasting to all connected users
            await manager.broadcast(notification)
            
            # Sending notifications to subscribers of a specific project topic
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"Processing error notification sent: {project_id} - {task_id} - {error_message}")
            
        except Exception as e:
            logger.error(f"Failed to send processing error notification: {e}")
    
    @staticmethod
    async def send_processing_started(project_id: str, message: str = "Initiating video processing flow"):
        """Send processing started notification (alias method))"""
        await WebSocketNotificationService.send_project_update(
            project_id=project_id,
            status="processing",
            progress=0,
            message=message
        )

# Global notification service instance
notification_service = WebSocketNotificationService()