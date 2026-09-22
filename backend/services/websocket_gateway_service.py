"""
WebSocketGateway service
Subscribe to Redis progress events and relay them to frontend WebSocket connections
Support message adaptation, snapshot replay, idempotent subscriptions
"""

import json
import logging
import asyncio
from typing import Dict, Set, Any, Optional, Callable
from datetime import datetime
import redis.asyncio as redis
from ..core.config import get_redis_url
from ..core.websocket_manager import manager
from .progress_event_service import ProgressEvent, progress_event_service
from .progress_message_adapter import progress_adapter
from .progress_snapshot_service import snapshot_service
from ..shared.progress_channels import normalize_channel, project_progress_channel

logger = logging.getLogger(__name__)

class WebSocketGatewayService:
    """WebSocketGateway service"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.channels_ref: Dict[str, int] = {}  # channel -> refcount
        self.router: Dict[str, Set[Callable]] = {}  # channel -> set of senders
        self.user_subscriptions: Dict[str, Set[str]] = {}  # user_id -> set of normalized channels
        self.lock = asyncio.Lock()
        self.listen_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Throttling control
        self.last_progress: Dict[str, Dict[str, Any]] = {}  # channel -> {progress, timestamp}
        self.throttle_interval = 0.2  # 200msMinimum interval
    
    @staticmethod
    def normalize_channel(raw: str) -> str:
        """
        Normalize channel name using unified naming convention
        
        Args:
            raw: Original channel name
            
        Returns:
            Normalized channel name: {title}
        """
        return normalize_channel(raw)
        
    async def start(self):
        """Start gateway service"""
        if self.is_running:
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
            self.is_running = True
            
            # Start snapshot service
            await snapshot_service.connect()
            
            # Start listening loop
            self.listen_task = asyncio.create_task(self._listen_loop())
            
            logger.info("WebSocketGateway service has started")
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket gateway service: {e}")
            self.is_running = False
    
    async def stop(self):
        """Stop gateway service"""
        self.is_running = False
        
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            await self.pubsub.aclose()  # redis-py 5.x Correct method
        
        if self.redis_client:
            await self.redis_client.aclose()  # redis-py 5.x Correct method
        
        # Stop snapshot service
        await snapshot_service.disconnect()
        
        logger.info("WebSocketGateway service has stopped")
    
    async def sync_user_subscriptions(self, user_id: str, channels: Set[str]) -> Dict[str, int]:
        """
        Idempotent operation: Synchronize user subscriptions
        
        Args:
            user_id: UserID
            channels: Channels to subscribe (raw format, will auto-normalize))
            
        Returns:
            Operation statistics: {"added": X, "removed": Y, "unchanged": Z}
        """
        async with self.lock:
            # 1) Normalize all channel names
            desired = {self.normalize_channel(ch) for ch in channels}
            current = self.user_subscriptions.get(user_id, set())
            
            # 2) Compute difference set
            to_add = desired - current
            to_remove = current - desired
            unchanged = current & desired
            
            # 3) Statistics
            added, removed, same = len(to_add), len(to_remove), len(unchanged)
            
            # 4) Process new subscriptions
            for channel in to_add:
                try:
                    await self._subscribe_to_channel(channel)
                    current.add(channel)  # Update local collection immediately
                    # Replay snapshot immediately
                    await self._replay_snapshot(user_id, channel)
                except Exception as e:
                    logger.error(f"Subscribe channel failed {channel}: {e}")
            
            # 5) Process removed subscriptions
            for channel in to_remove:
                try:
                    await self._unsubscribe_from_channel(channel)
                    current.discard(channel)  # Delete local collection immediately
                except Exception as e:
                    logger.error(f"Failed to unsubscribe from channel {channel}: {e}")
            
            # 6) Update user subscription record (use normalized set)
            self.user_subscriptions[user_id] = current
            
            # 7) Log de-noising: only INFO on change
            if added or removed:
                logger.info(f"Subscription set synchronized: User {user_id}, Added {added}, Remove {removed}, No change {same}")
            else:
                logger.debug(f"Subscribers sync complete (no changes): Users {user_id}, No change {same}")
            
            return {
                "added": added,
                "removed": removed, 
                "unchanged": same
            }
    
    async def _subscribe_to_channel(self, channel: str):
        """Subscribe channel"""
        if channel not in self.channels_ref:
            self.channels_ref[channel] = 0
            await self.pubsub.subscribe(channel)
            logger.debug(f"Subscribed channel: {channel}")
        
        self.channels_ref[channel] += 1
    
    async def _unsubscribe_from_channel(self, channel: str):
        """Cancel channel subscription"""
        if channel in self.channels_ref:
            self.channels_ref[channel] -= 1
            if self.channels_ref[channel] <= 0:
                await self.pubsub.unsubscribe(channel)
                del self.channels_ref[channel]
                logger.debug(f"Unsubscribed from channel {file}: {channel}")
    
    async def _replay_snapshot(self, user_id: str, channel: str):
        """Replay snapshot"""
        try:
            snapshot = await snapshot_service.get_snapshot(channel)
            if snapshot:
                # Convert to short message
                simple_msg = progress_adapter.to_simple(snapshot)
                simple_msg["snapshot"] = True
                
                # Send to user
                await manager.send_personal_message(simple_msg, user_id)
                logger.debug(f"Snapshot replayed: {user_id} -> {channel}")
        except Exception as e:
            logger.error(f"Failed to replay snapshot: {e}")
    
    async def subscribe_user_to_task(self, user_id: str, task_id: str) -> bool:
        """User subscription progress for specific task"""
        try:
            # Normalize channel name - use Project ID instead of Task ID
            # Need to infer project_id from task_id, or modify call signature
            # Using temporary task_id but should use project_id instead
            channel = project_progress_channel(task_id)
            
            # Record user subscription
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
            self.user_subscriptions[user_id].add(channel)
            
            # Create sender function - use user ID as identifier
            async def sender(data: str):
                try:
                    logger.debug(f"Sender received data: {data}")
                    message_data = json.loads(data)
                    logger.debug(f"Parsed message: {message_data}")
                    
                    # Construct WebSocket message
                    ws_message = {
                        "type": "task_progress_update",
                        "task_id": message_data.get("task_id"),
                        "progress": message_data.get("progress"),
                        "step": message_data.get("step"),
                        "total": message_data.get("total"),
                        "phase": message_data.get("phase"),
                        "message": message_data.get("message"),
                        "status": message_data.get("status"),
                        "seq": message_data.get("seq"),
                        "ts": message_data.get("ts"),
                        "meta": message_data.get("meta"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    await manager.send_personal_message(ws_message, user_id)
                    logger.debug(f"Message sent to user {user_id}")
                except Exception as e:
                    logger.error(f"Send message to user {e} {user_id} Failed: {e}")
            
            # Add identifier to sender for matching
            sender._user_id = user_id
            sender._task_id = task_id
            
            # Subscribe channel
            await self._subscribe_channel(channel, sender)
            
            # Send subscription confirmation
            await manager.send_personal_message({
                "type": "subscription_confirmed",
                "task_id": task_id,
                "message": f"Subscribed task {task_id} Progress update for",
                "timestamp": datetime.utcnow().isoformat()
            }, user_id)
            
            # Send snapshot (if exists)
            try:
                from .progress_event_service import progress_event_service
                snapshot = await progress_event_service.get_task_snapshot(task_id)
                if snapshot:
                    snapshot_message = {
                        "type": "task_progress_update",
                        **snapshot,
                        "snapshot": True  # Mark as snapshot message
                    }
                    await manager.send_personal_message(snapshot_message, user_id)
                    logger.debug(f"Task already sent {task_id} Snapshot for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send task snapshot: {e}")
            
            logger.debug(f"User {user_id} Subscribed task {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Subscribe task failed for user {e}: {e}")
            return False
    
    async def unsubscribe_user_from_task(self, user_id: str, task_id: str) -> bool:
        """User unsubscribed from specific task progress"""
        try:
            channel = f"progress:{task_id}"
            
            # Create sender function (for matching)
            async def sender(data: str):
                try:
                    await manager.send_personal_message(json.loads(data), user_id)
                except Exception as e:
                    logger.error(f"Send message to user {e} {user_id} Failed: {e}")
            
            # Cancel channel subscription
            await self._unsubscribe_channel(channel, sender)
            
            # Send unsubscribe confirmation
            await manager.send_personal_message({
                "type": "unsubscription_confirmed",
                "task_id": task_id,
                "message": f"Unsubscribe task canceled {task_id} Progress update for",
                "timestamp": datetime.utcnow().isoformat()
            }, user_id)
            
            logger.debug(f"User {user_id} Unsubscribe task canceled {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe user from task: {e}")
            return False
    
    async def unsubscribe_user_from_all_tasks(self, user_id: str):
        """Cancel all subscriptions when user disconnects"""
        if user_id in self.user_subscriptions:
            task_ids = list(self.user_subscriptions[user_id])
            for task_id in task_ids:
                await self.unsubscribe_user_from_task(user_id, task_id)
            del self.user_subscriptions[user_id]
            logger.info(f"User {user_id} Cancelled all task subscriptions")

    async def subscribe_user_to_many_tasks(self, user_id: str, task_ids: list[str]) -> dict:
        """Batch subscribe multiple tasks - idempotent operation"""
        results = {"added": [], "already_subscribed": []}
        
        for task_id in task_ids:
            # Check if already subscribed
            if user_id in self.user_subscriptions and task_id in self.user_subscriptions[user_id]:
                results["already_subscribed"].append(task_id)
                logger.debug(f"User {user_id} Subscribed task {task_id}, Skip")
                continue
            
            # Execute subscription
            if await self.subscribe_user_to_task(user_id, task_id):
                results["added"].append(task_id)
            else:
                logger.error(f"User {user_id} Subscription task {task_id} Failed")
        
        logger.info(f"Bulk subscribe completed: User {user_id}, Added {len(results['added'])}, Already exists {len(results['already_subscribed'])}")
        return results

    async def unsubscribe_user_from_many_tasks(self, user_id: str, task_ids: list[str]) -> dict:
        """Bulk unsubscribe multiple tasks"""
        results = {"removed": [], "not_subscribed": []}
        
        for task_id in task_ids:
            # Check if already subscribed
            if user_id not in self.user_subscriptions or task_id not in self.user_subscriptions[user_id]:
                results["not_subscribed"].append(task_id)
                logger.debug(f"User {user_id} Unsubscribed task {task_id}, Skip")
                continue
            
            # Execute unsubscribe
            if await self.unsubscribe_user_from_task(user_id, task_id):
                results["removed"].append(task_id)
            else:
                logger.error(f"User {user_id} Unsubscribe task {task_id} Failed")
        
        logger.info(f"Bulk unsubscribe completed: User {user_id}, Remove {len(results['removed'])}, Not subscribed {len(results['not_subscribed'])}")
        return results

    async def sync_user_subscriptions(self, user_id: str, desired_task_ids: list[str]) -> dict:
        """Sync user subscribers - idempotent alignment"""
        current_task_ids = list(self.user_subscriptions.get(user_id, set()))
        desired_set = set(desired_task_ids)
        current_set = set(current_task_ids)
        
        # Calculate difference
        to_add = list(desired_set - current_set)
        to_remove = list(current_set - desired_set)
        
        results = {"added": [], "removed": [], "unchanged": []}
        
        # Batch add
        if to_add:
            add_results = await self.subscribe_user_to_many_tasks(user_id, to_add)
            results["added"] = add_results["added"]
        
        # Batch remove
        if to_remove:
            remove_results = await self.unsubscribe_user_from_many_tasks(user_id, to_remove)
            results["removed"] = remove_results["removed"]
        
        # Unchanged
        results["unchanged"] = list(desired_set & current_set)
        
        # Log only on actual change to avoid noise
        if len(results['added']) > 0 or len(results['removed']) > 0:
            logger.info(f"Subscription set synchronized: User {user_id}, Added {len(results['added'])}, Remove {len(results['removed'])}, No change {len(results['unchanged'])}")
        else:
            logger.debug(f"Subscription set synchronized: User {user_id}, Added {len(results['added'])}, Remove {len(results['removed'])}, No change {len(results['unchanged'])}")
        return results
    
    async def _subscribe_channel(self, channel: str, sender: Callable):
        """Subscribe to Redis channel - idempotent operation"""
        async with self.lock:
            # Check if already subscribed to this channel
            if sender in self.router.get(channel, set()):
                logger.debug(f"Sender already subscribed to channel {channel}, Skip")
                return
            
            need_sub = channel not in self.channels_ref
            self.channels_ref[channel] = self.channels_ref.get(channel, 0) + 1
            self.router.setdefault(channel, set()).add(sender)
            
            if need_sub:
                await self.pubsub.subscribe(channel)
                logger.info(f"[Redis] SUB {channel}; total={len(self.channels_ref)}")
            else:
                logger.debug(f"[Redis] Channel {channel} Existing subscriber, adding sender")
    
    async def _unsubscribe_channel(self, channel: str, sender: Callable):
        """Unsubscribe from Redis channel"""
        async with self.lock:
            if channel in self.router:
                self.router[channel].discard(sender)
            
            if channel in self.channels_ref:
                self.channels_ref[channel] -= 1
                if self.channels_ref[channel] <= 0:
                    del self.channels_ref[channel]
                    self.router.pop(channel, None)
                    await self.pubsub.unsubscribe(channel)
                    logger.info(f"[Redis] UNSUB {channel}; total={len(self.channels_ref)}")
    
    async def _listen_loop(self):
        """Listen to Redis messages loop - integrate message adapter and throttling control"""
        backoff = 0.05
        
        while self.is_running:
            try:
                # Check for existing channels with subscriptions
                async with self.lock:
                    has_channels = bool(self.channels_ref)
                
                if not has_channels:
                    await asyncio.sleep(0.2)
                    continue
                
                # Getting messages - correct way with redis-py 5.x
                msg = await self.pubsub.get_message(timeout=0.1)
                
                if not msg or msg["type"] != "message":
                    await asyncio.sleep(0.05)  # Sleep briefly to avoid high CPU usage
                    continue
                
                channel = msg["channel"]
                data = msg["data"]
                
                # Parse message
                try:
                    message_data = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Parsing message failed: {e}, Data: {data}")
                    continue
                
                # Check if message is a progress update
                if not progress_adapter.is_progress_message(message_data):
                    logger.debug(f"Skip non-progress message: {message_data.get('type', 'unknown')}")
                    continue
                
                # Throttling control
                current_time = datetime.utcnow().timestamp()
                current_progress = message_data.get("progress", 0)
                
                if channel in self.last_progress:
                    last_data = self.last_progress[channel]
                    if progress_adapter.should_throttle(
                        last_data["progress"], current_progress,
                        last_data["timestamp"], current_time,
                        self.throttle_interval
                    ):
                        logger.debug(f"Message is throttled: {channel} - {current_progress}%")
                        continue
                
                # Update throttle record
                self.last_progress[channel] = {
                    "progress": current_progress,
                    "timestamp": current_time
                }
                
                # Convert to short message
                simple_msg = progress_adapter.to_simple(message_data)
                
                # Get target user from subscriber channel
                async with self.lock:
                    subscribed_users = set()
                    for user_id, user_channels in self.user_subscriptions.items():
                        if channel in user_channels:
                            subscribed_users.add(user_id)
                
                # Send to all subscribed users
                if subscribed_users:
                    logger.debug(f"Forward short message to {len(subscribed_users)} users: {channel} - {simple_msg}")
                    
                    # Concurrent sending
                    send_tasks = []
                    for user_id in subscribed_users:
                        send_tasks.append(
                            manager.send_personal_message(simple_msg, user_id)
                        )
                    
                    if send_tasks:
                        await asyncio.gather(*send_tasks, return_exceptions=True)
                else:
                    logger.debug(f"Channel {channel} No subscribed users")
                
                backoff = 0.05  # Reset backoff time
                
            except Exception as e:
                logger.error(f"Failed to process Redis message: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 1.0)  # Exponential backoff, max 1 second
    
    async def get_subscription_status(self, user_id: str) -> Dict[str, Any]:
        """Get user subscription status"""
        async with self.lock:
            return {
                "user_id": user_id,
                "subscribed_tasks": [],  # Simplified implementation
                "total_subscriptions": 0,
                "active_channels": len(self.channels_ref)
            }

# Global instance
websocket_gateway_service = WebSocketGatewayService()
