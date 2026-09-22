"""
Offline mode supportAPI
Provides network status detection, offline mode management, and caching
"""
import os
import time
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.core.desktop_config import is_desktop_mode

router = APIRouter()

# check desktop mode
def check_desktop_mode():
    if not is_desktop_mode():
        raise HTTPException(status_code=400, detail="This endpoint is only available in desktop mode")

class NetworkStatus(BaseModel):
    """network status model"""
    is_online: bool
    connection_quality: str  # excellent, good, poor, offline
    latency: Optional[float] = None
    last_check: str
    error_message: Optional[str] = None

class OfflineModeStatus(BaseModel):
    """Offline mode state model"""
    is_offline_mode: bool
    auto_offline_threshold: int  # continuous failure threshold
    consecutive_failures: int
    last_successful_request: Optional[str] = None
    offline_since: Optional[str] = None

class CacheItem(BaseModel):
    """Cache item model"""
    key: str
    data: Any
    created_at: str
    expires_at: Optional[str] = None
    size: int

class SyncQueueItem(BaseModel):
    """sync queue item model"""
    id: str
    action: str  # create, update, delete
    resource_type: str  # project, clip, collection
    resource_id: str
    data: Dict[str, Any]
    created_at: str
    retry_count: int = 0
    max_retries: int = 3

# In-memory state storage (in production, use persistent storage))
_network_status = NetworkStatus(
    is_online=True,
    connection_quality="good",
    last_check=datetime.now().isoformat()
)

_offline_mode_status = OfflineModeStatus(
    is_offline_mode=False,
    auto_offline_threshold=3,
    consecutive_failures=0
)

_cache: Dict[str, CacheItem] = {}
_sync_queue: List[SyncQueueItem] = []

@router.get("/network/status", response_model=NetworkStatus)
async def get_network_status():
    """get network status"""
    check_desktop_mode()
    
    try:
        # Test network connection
        start_time = time.time()
        response = requests.get("https://www.google.com", timeout=5)
        latency = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        if response.status_code == 200:
            # Determine connection quality based on latency
            if latency < 100:
                quality = "excellent"
            elif latency < 500:
                quality = "good"
            else:
                quality = "poor"
            
            _network_status.is_online = True
            _network_status.connection_quality = quality
            _network_status.latency = latency
            _network_status.last_check = datetime.now().isoformat()
            _network_status.error_message = None
            
            # Reset consecutive failure count
            _offline_mode_status.consecutive_failures = 0
            _offline_mode_status.last_successful_request = datetime.now().isoformat()
            
        else:
            raise requests.RequestException(f"HTTP {response.status_code}")
            
    except Exception as e:
        # Network connection failed
        _network_status.is_online = False
        _network_status.connection_quality = "offline"
        _network_status.latency = None
        _network_status.last_check = datetime.now().isoformat()
        _network_status.error_message = str(e)
        
        # increase consecutive failures counter
        _offline_mode_status.consecutive_failures += 1
        
        # Check if auto-enter offline mode should be triggered
        if (_offline_mode_status.consecutive_failures >= _offline_mode_status.auto_offline_threshold 
            and not _offline_mode_status.is_offline_mode):
            _offline_mode_status.is_offline_mode = True
            _offline_mode_status.offline_since = datetime.now().isoformat()
    
    return _network_status

@router.get("/offline/status", response_model=OfflineModeStatus)
async def get_offline_mode_status():
    """get offline mode status"""
    check_desktop_mode()
    return _offline_mode_status

@router.post("/offline/toggle")
async def toggle_offline_mode():
    """Switch to offline mode"""
    check_desktop_mode()
    
    _offline_mode_status.is_offline_mode = not _offline_mode_status.is_offline_mode
    
    if _offline_mode_status.is_offline_mode:
        _offline_mode_status.offline_since = datetime.now().isoformat()
    else:
        _offline_mode_status.offline_since = None
        _offline_mode_status.consecutive_failures = 0
    
    return {
        "is_offline_mode": _offline_mode_status.is_offline_mode,
        "message": "offline mode has been opened" if _offline_mode_status.is_offline_mode else "offline mode has been closed"
    }

@router.post("/offline/auto-threshold")
async def set_auto_offline_threshold(threshold: int):
    """Set auto-offline threshold"""
    check_desktop_mode()
    
    if threshold < 1 or threshold > 10:
        raise HTTPException(status_code=400, detail="Threshold must be between1-10Between")
    
    _offline_mode_status.auto_offline_threshold = threshold
    
    return {
        "auto_offline_threshold": threshold,
        "message": f"Auto-offline threshold set to {threshold}"
    }

@router.get("/cache", response_model=List[CacheItem])
async def get_cache_items():
    """get cache item list"""
    check_desktop_mode()
    
    # clean expired cache
    current_time = datetime.now()
    expired_keys = []
    
    for key, item in _cache.items():
        if item.expires_at:
            expires_at = datetime.fromisoformat(item.expires_at)
            if current_time > expires_at:
                expired_keys.append(key)
    
    for key in expired_keys:
        del _cache[key]
    
    return list(_cache.values())

@router.post("/cache")
async def add_cache_item(key: str, data: Any, expires_in_seconds: Optional[int] = None):
    """Add cache item"""
    check_desktop_mode()
    
    created_at = datetime.now().isoformat()
    expires_at = None
    
    if expires_in_seconds:
        expires_at = (datetime.now() + timedelta(seconds=expires_in_seconds)).isoformat()
    
    # Compute data size (simple estimate))
    size = len(str(data))
    
    _cache[key] = CacheItem(
        key=key,
        data=data,
        created_at=created_at,
        expires_at=expires_at,
        size=size
    )
    
    return {
        "key": key,
        "message": "cache item added",
        "expires_at": expires_at
    }

@router.delete("/cache/{key}")
async def remove_cache_item(key: str):
    """Delete cache item"""
    check_desktop_mode()
    
    if key in _cache:
        del _cache[key]
        return {"message": f"Cache item {key} Deleted"}
    else:
        raise HTTPException(status_code=404, detail="Cache item does not exist")

@router.get("/sync-queue", response_model=List[SyncQueueItem])
async def get_sync_queue():
    """get sync queue"""
    check_desktop_mode()
    return _sync_queue

@router.post("/sync-queue")
async def add_sync_queue_item(
    action: str,
    resource_type: str,
    resource_id: str,
    data: Dict[str, Any]
):
    """add sync queue item"""
    check_desktop_mode()
    
    if action not in ["create", "update", "delete"]:
        raise HTTPException(status_code=400, detail="invalid operation type")
    
    if resource_type not in ["project", "clip", "collection"]:
        raise HTTPException(status_code=400, detail="invalid resource type")
    
    item = SyncQueueItem(
        id=f"{resource_type}_{resource_id}_{int(time.time())}",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
        created_at=datetime.now().isoformat()
    )
    
    _sync_queue.append(item)
    
    return {
        "id": item.id,
        "message": "Sync queue item added"
    }

@router.post("/sync-queue/process")
async def process_sync_queue():
    """Process sync queue"""
    check_desktop_mode()
    
    if _offline_mode_status.is_offline_mode:
        return {
            "message": "Currently in offline mode, unable to process sync queue",
            "queue_size": len(_sync_queue)
        }
    
    processed = 0
    failed = 0
    
    for item in _sync_queue[:]:  # Use slice copy to avoid modifying lists
        try:
            # Call actualAPITo sync data
            # To demonstrate, we simulate a simple processing workflow
            await simulate_sync_operation(item)
            
            _sync_queue.remove(item)
            processed += 1
            
        except Exception as e:
            item.retry_count += 1
            if item.retry_count >= item.max_retries:
                _sync_queue.remove(item)
                failed += 1
            else:
                # Keep in queue pending retry attempts
                pass
    
    return {
        "processed": processed,
        "failed": failed,
        "remaining": len(_sync_queue),
        "message": f"processing completed: success {processed} failed operations {failed} unit"
    }

async def simulate_sync_operation(item: SyncQueueItem):
    """Simulate sync operation"""
    # In actual implementation, call appropriateAPIendpoint
    # For example: create project, update fragment, delete collection, etc.
    await asyncio.sleep(0.1)  # simulate network delay
    
    # simulate occasional failure
    import random
    if random.random() < 0.1:  # 10% of failure rate
        raise Exception("simulate network error")

@router.delete("/sync-queue/clear")
async def clear_sync_queue():
    """Clear sync queue"""
    check_desktop_mode()
    
    count = len(_sync_queue)
    _sync_queue.clear()
    
    return {
        "message": f"Sync queue has been cleared, removed {count} items"
    }

@router.get("/offline/summary")
async def get_offline_summary():
    """Get offline mode summary information"""
    check_desktop_mode()
    
    return {
        "network_status": _network_status,
        "offline_mode_status": _offline_mode_status,
        "cache_stats": {
            "total_items": len(_cache),
            "total_size": sum(item.size for item in _cache.values()),
            "expired_items": len([
                item for item in _cache.values() 
                if item.expires_at and datetime.fromisoformat(item.expires_at) < datetime.now()
            ])
        },
        "sync_queue_stats": {
            "total_items": len(_sync_queue),
            "pending_items": len([item for item in _sync_queue if item.retry_count < item.max_retries]),
            "failed_items": len([item for item in _sync_queue if item.retry_count >= item.max_retries])
        }
    }
