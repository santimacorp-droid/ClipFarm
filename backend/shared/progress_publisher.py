"""
Unified progress publishing service
Provide a standardized progress event publishing interface
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional
import redis.asyncio as redis
from .progress_channels import project_progress_channel
from ..core.config import get_redis_url

logger = logging.getLogger(__name__)

class ProgressPublisher:
    """Unified progress publisher"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
    
    async def _get_redis_client(self) -> redis.Redis:
        """Get Redis client"""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client
    
    async def publish_project_progress(
        self, 
        project_id: str, 
        step: int, 
        total_steps: int, 
        percent: float, 
        message: str, 
        status: str = "running",
        task_id: Optional[str] = None
    ) -> bool:
        """
        Publish project progress events
        
        Args:
            project_id: ProjectID
            step: Current step
            total_steps: Total steps
            percent: Progress percentage (0-100)
            message: Progress message
            status: Status (running/succeeded/failed)
            task_id: Task ID (optional))
            
        Returns:
            Whether publish succeeded
        """
        try:
            channel = project_progress_channel(project_id)
            payload = {
                "type": "project_progress",
                "projectId": project_id,
                "step": step,
                "totalSteps": total_steps,
                "percent": percent,
                "message": message,
                "status": status,
                "ts": time.time()
            }
            
            if task_id:
                payload["taskId"] = task_id
            
            redis_client = await self._get_redis_client()
            await redis_client.publish(channel, json.dumps(payload, ensure_ascii=False))
            
            logger.info(f"Progress event published successfully: {project_id} - {percent}% - {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish progress event: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

# Global instance
progress_publisher = ProgressPublisher()

# Convenience function
async def publish_project_progress(
    project_id: str, 
    step: int, 
    total_steps: int, 
    percent: float, 
    message: str, 
    status: str = "running",
    task_id: Optional[str] = None
) -> bool:
    """Publish project progress with a convenient function"""
    return await progress_publisher.publish_project_progress(
        project_id, step, total_steps, percent, message, status, task_id
    )
