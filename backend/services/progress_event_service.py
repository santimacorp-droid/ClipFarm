"""
Progress event service
Implement task progress synchronization using Redis PubSub
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
import redis.asyncio as redis
from ..core.config import get_redis_url
from ..shared.progress_channels import project_progress_channel

logger = logging.getLogger(__name__)

@dataclass
class ProgressEvent:
    """Progress event data structure"""
    task_id: str
    progress: int  # 0-100
    step: int
    total: int
    phase: str  # transcribe|analyze|clip|encode|upload
    message: str
    status: str  # PENDING|PROGRESS|DONE|FAIL
    seq: int  # Increment sequence number
    ts: float  # Monotonic increasing timestamp
    meta: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressEvent':
        """Create instance from dictionary"""
        return cls(**data)

class ProgressEventService:
    """Progress event service"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self.sequence_counters: Dict[str, int] = {}  # Counter for per-task_id sequence numbers
        self.throttle_cache: Dict[str, Dict[str, Any]] = {}  # Throttle cache
        self.throttle_interval = 0.2  # 200msThrottle interval
        
    async def _get_redis_client(self) -> redis.Redis:
        """Obtain Redis client"""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client
    
    def _get_next_seq(self, task_id: str) -> int:
        """Get next sequence number"""
        if task_id not in self.sequence_counters:
            self.sequence_counters[task_id] = 0
        self.sequence_counters[task_id] += 1
        return self.sequence_counters[task_id]
    
    def _should_throttle(self, task_id: str, progress: int) -> bool:
        """Check if throttling is needed"""
        now = time.time()
        cache_key = f"{task_id}_{progress}"
        
        if cache_key in self.throttle_cache:
            last_time = self.throttle_cache[cache_key]['timestamp']
            if now - last_time < self.throttle_interval:
                return True
        
        # Update cache
        self.throttle_cache[cache_key] = {
            'timestamp': now,
            'progress': progress
        }
        
        # Clean up expired cache (items older than 1 minute)
        expired_keys = [
            key for key, data in self.throttle_cache.items()
            if now - data['timestamp'] > 60
        ]
        for key in expired_keys:
            del self.throttle_cache[key]
        
        return False
    
    async def report_progress(
        self,
        task_id: str,
        progress: int,
        step: int,
        total: int,
        phase: str,
        message: str,
        status: str = "PROGRESS",
        meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Report task progress"""
        try:
            # Throttle check
            if status == "PROGRESS" and self._should_throttle(task_id, progress):
                logger.debug(f"Task {task_id} Progress {progress}% Throttled")
                return True
            
            # Create progress event
            event = ProgressEvent(
                task_id=task_id,
                progress=progress,
                step=step,
                total=total,
                phase=phase,
                message=message,
                status=status,
                seq=self._get_next_seq(task_id),
                ts=time.time(),
                meta=meta
            )
            
            # Publish on Redis channel - use project ID instead of task ID
            # Extract project_id from task_id or use the one in meta
            project_id = meta.get("project_id") if meta else None
            if not project_id:
                # If meta has no project_id, attempt to infer from task_id
                # Adjust according to specific needs here
                project_id = task_id  # Temporarily use task_id; will need optimization later
            channel = project_progress_channel(project_id)
            redis_client = await self._get_redis_client()
            
            # Simultaneously save snapshot to Redis Hash
            snapshot_key = f"progress:last:{channel}"
            event_dict = event.to_dict()
            
            # Filter out None values and convert all remaining values to strings to avoid Redis storage errors
            filtered_dict = {}
            for k, v in event_dict.items():
                if v is not None:
                    if isinstance(v, dict):
                        # Convert dictionary to JSON string
                        filtered_dict[k] = json.dumps(v, ensure_ascii=False)
                    else:
                        filtered_dict[k] = str(v)
            
            await redis_client.hset(snapshot_key, mapping=filtered_dict)
            await redis_client.expire(snapshot_key, 3600)  # 1Hour expiration
            
            # Publish to channel
            await redis_client.publish(channel, json.dumps(event_dict))
            
            logger.info(f"Progress event published: {task_id} - {progress}% - {phase} - seq:{event.seq}")
            return True
            
        except Exception as e:
            logger.error(f"Publish progress event failed: {e}")
            return False
    
    async def subscribe_to_task(
        self,
        task_id: str,
        callback: Callable[[ProgressEvent], None]
    ) -> bool:
        """Subscribe to progress events for a specific task"""
        try:
            channel = f"progress:{task_id}"
            redis_client = await self._get_redis_client()
            
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            logger.info(f"Already subscribed to task progress channel: {channel}")
            
            # Handle message asynchronously
            async def message_handler():
                try:
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            try:
                                data = json.loads(message['data'])
                                event = ProgressEvent.from_dict(data)
                                callback(event)
                            except Exception as e:
                                logger.error(f"Handling progress event failed: {e}")
                except Exception as e:
                    logger.error(f"Subscribe to message handling failed: {e}")
                finally:
                    await pubsub.unsubscribe(channel)
                    await pubsub.close()
            
            # Start message processing coroutine
            asyncio.create_task(message_handler())
            return True
            
        except Exception as e:
            logger.error(f"Subscribe to task progress failed: {e}")
            return False
    
    async def get_task_snapshot(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task progress snapshot"""
        try:
            redis_client = await self._get_redis_client()
            channel = f"progress:{task_id}"
            snapshot_key = f"progress:last:{channel}"
            snapshot = await redis_client.hgetall(snapshot_key)
            if snapshot:
                # Convert string values back to appropriate types
                if 'progress' in snapshot:
                    snapshot['progress'] = int(snapshot['progress'])
                if 'step' in snapshot:
                    snapshot['step'] = int(snapshot['step'])
                if 'total' in snapshot:
                    snapshot['total'] = int(snapshot['total'])
                if 'seq' in snapshot:
                    snapshot['seq'] = int(snapshot['seq'])
                if 'ts' in snapshot:
                    snapshot['ts'] = float(snapshot['ts'])
                return snapshot
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve task progress snapshot: {e}")
            return None

    async def get_task_final_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve final task status (for end-state calibration))"""
        try:
            redis_client = await self._get_redis_client()
            key = f"task_final_state:{task_id}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to obtain final task status: {e}")
            return None
    
    async def save_task_final_state(self, task_id: str, state: Dict[str, Any]) -> bool:
        """Save task final status"""
        try:
            redis_client = await self._get_redis_client()
            key = f"task_final_state:{task_id}"
            await redis_client.setex(key, 3600, json.dumps(state))  # 1Hour expiration
            return True
        except Exception as e:
            logger.error(f"Failed to save task final status: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

# Global instance
progress_event_service = ProgressEventService()

# Convenience function
async def report_progress(
    task_id: str,
    progress: int,
    step: int,
    total: int,
    phase: str,
    message: str,
    status: str = "PROGRESS",
    meta: Optional[Dict[str, Any]] = None
) -> bool:
    """Convenience function to report task progress"""
    return await progress_event_service.report_progress(
        task_id, progress, step, total, phase, message, status, meta
    )

