"""
Progress snapshot service
Manage Redis snapshot storage and replay
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import redis.asyncio as redis
from ..core.config import get_redis_url

logger = logging.getLogger(__name__)

class ProgressSnapshotService:
    """Progress snapshot service"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self):
        """connecting to Redis"""
        if self._connected:
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            self._connected = True
            logger.info("Progress snapshot service connectedRedis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
    
    async def disconnect(self):
        """Disconnected from Redis"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
        self._connected = False
        logger.info("Progress snapshot service disconnectedRedis")
    
    def _get_snapshot_key(self, channel: str) -> str:
        """Getting snapshot key name"""
        return f"progress:last:{channel}"
    
    async def save_snapshot(self, channel: str, payload: dict) -> bool:
        """
        Save progress snapshot
        
        Args:
            channel: channel name
            payload: message payload
            
        Returns:
            Whether save was successful
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return False
        
        try:
            snapshot_key = self._get_snapshot_key(channel)
            
            # adding timestamp
            payload_with_ts = {
                **payload,
                "snapshot_timestamp": datetime.utcnow().isoformat()
            }
            
            # Save to Redis Hash
            await self.redis_client.hset(snapshot_key, mapping=payload_with_ts)
            
            # Set expiration time (24 hours)
            await self.redis_client.expire(snapshot_key, 86400)
            
            logger.debug(f"Snapshot saved: {channel} -> {snapshot_key}")
            return True
            
        except Exception as e:
            logger.error(f"Saving snapshot failed: {e}")
            return False
    
    async def get_snapshot(self, channel: str) -> Optional[dict]:
        """
        getting progress snapshot
        
        Args:
            channel: channel name
            
        Returns:
            snapshot data or None
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return None
        
        try:
            snapshot_key = self._get_snapshot_key(channel)
            snapshot_data = await self.redis_client.hgetall(snapshot_key)
            
            if snapshot_data:
                logger.debug(f"Snapshot retrieved: {channel} -> {snapshot_data}")
                return snapshot_data
            else:
                logger.debug(f"Snapshot does not exist: {channel}")
                return None
                
        except Exception as e:
            logger.error(f"Get snapshot failed: {e}")
            return None
    
    async def delete_snapshot(self, channel: str) -> bool:
        """
        Delete progress snapshot
        
        Args:
            channel: channel name
            
        Returns:
            Whether delete was successful
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return False
        
        try:
            snapshot_key = self._get_snapshot_key(channel)
            result = await self.redis_client.delete(snapshot_key)
            
            if result:
                logger.debug(f"Snapshot deleted: {channel}")
            else:
                logger.debug(f"Snapshot does not exist; no deletion required: {channel}")
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Deleting snapshot failed: {e}")
            return False
    
    async def cleanup_expired_snapshots(self) -> int:
        """
        Cleaning up expired snapshots
        
        Returns:
            Number of snapshots cleaned
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return 0
        
        try:
            # Looking up all snapshot keys
            pattern = "progress:last:*"
            keys = await self.redis_client.keys(pattern)
            
            cleaned_count = 0
            for key in keys:
                # Check if expired
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # No expiration set
                    await self.redis_client.expire(key, 86400)  # Set 24 hour expiration
                elif ttl == -2:  # key does not exist
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} Expired snapshot(s)")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to clean up expired snapshots: {e}")
            return 0

# Global snapshot service instance
snapshot_service = ProgressSnapshotService()
