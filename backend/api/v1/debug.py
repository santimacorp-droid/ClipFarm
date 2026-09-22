"""
DebugAPIInterface for testing and debugging functionality
"""

import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import redis.asyncio as redis
from ...core.config import get_redis_url

logger = logging.getLogger(__name__)
router = APIRouter()

class PublishMessage(BaseModel):
    """Message publication model"""
    task_id: str
    progress: int
    step: int = 1
    total: int = 6
    phase: str = "test"
    message: str = "Debug message"
    status: str = "PROGRESS"
    seq: int = 1
    meta: Dict[str, Any] = {}

@router.post("/debug/publish")
async def debug_publish_message(message: PublishMessage):
    """Debug interface: Publish progress message toRedis"""
    try:
        # ConnectRedis
        redis_client = redis.from_url(get_redis_url(), decode_responses=True)
        
        # Build message
        import time
        full_message = {
            "task_id": message.task_id,
            "progress": message.progress,
            "step": message.step,
            "total": message.total,
            "phase": message.phase,
            "message": message.message,
            "status": message.status,
            "seq": message.seq,
            "ts": time.time(),
            "meta": message.meta
        }
        
        # Published toRedis
        channel = f"progress:{message.task_id}"
        result = await redis_client.publish(channel, json.dumps(full_message))
        
        await redis_client.aclose()
        
        logger.info(f"Debug published message: {channel} -> {result} subscriptions")
        
        return {
            "success": True,
            "channel": channel,
            "subscribers": result,
            "message": full_message
        }
        
    except Exception as e:
        logger.error(f"Debug publish message failed: {e}")
        raise HTTPException(status_code=500, detail=f"Publication failed: {str(e)}")

@router.get("/debug/subscriptions")
async def debug_get_subscriptions():
    """Debug interface: Get current subscription status"""
    try:
        from ...services.websocket_gateway_service import websocket_gateway_service
        
        async with websocket_gateway_service.lock:
            return {
                "success": True,
                "active_channels": len(websocket_gateway_service.channels_ref),
                "channels": dict(websocket_gateway_service.channels_ref),
                "user_subscriptions": dict(websocket_gateway_service.user_subscriptions)
            }
            
    except Exception as e:
        logger.error(f"Failed to get subscription status: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieve failed: {str(e)}")

@router.get("/debug/redis-info")
async def debug_redis_info():
    """Debug interface: GetRedisConnection information"""
    try:
        redis_url = get_redis_url()
        redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        await redis_client.ping()
        
        # Get information
        info = await redis_client.info()
        
        await redis_client.aclose()
        
        return {
            "success": True,
            "redis_url": redis_url,
            "redis_version": info.get("redis_version"),
            "connected_clients": info.get("connected_clients"),
            "used_memory": info.get("used_memory_human")
        }
        
    except Exception as e:
        logger.error(f"GetRedisInformation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieve failed: {str(e)}")

