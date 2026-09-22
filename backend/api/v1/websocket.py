"""
WebSocket APIRoute
"""

import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.websocket_manager import manager, WebSocketMessage
from ...services.websocket_notification_service import WebSocketNotificationService
from ...services.websocket_gateway_service import websocket_gateway_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocketConnection endpoint"""
    await manager.connect(websocket, user_id)
    
    try:
        # Send connection confirmation message
        welcome_message = WebSocketMessage.create_system_notification(
            "connection",
            "Connection established",
            f"User {user_id} Message broadcasted successfullyWebSocketService",
            "success"
        )
        await manager.send_personal_message(welcome_message, user_id)
        
        # Process client message - keep alive loop
        while True:
            try:
                # Receive client message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Process different types of messages
                await handle_client_message(user_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"User {user_id} Manually disconnected")
                break
            except json.JSONDecodeError:
                logger.error(f"User {user_id} Message has incorrect send format")
                try:
                    error_message = WebSocketMessage.create_error_notification(
                        "message_format_error",
                        "Invalid message format",
                        {"message": "Please send validJSONMessage formatted"}
                    )
                    await manager.send_personal_message(error_message, user_id)
                except:
                    # If sending fails, connection is already disconnected; directly exit
                    break
            except Exception as e:
                logger.error(f"User processor {user_id} Message timed out: {e}")
                try:
                    error_message = WebSocketMessage.create_error_notification(
                        "processing_error",
                        "Message processing error",
                        {"error": str(e)}
                    )
                    await manager.send_personal_message(error_message, user_id)
                except:
                    # If sending fails, connection is already disconnected; directly exit
                    break
    
    except WebSocketDisconnect:
        logger.info(f"User {user_id} Disconnected")
    except Exception as e:
        logger.error(f"WebSocketConnection exception occurred: {e}")
    finally:
        # Clean up in sequence: unsubscribe first, then disconnect
        try:
            await websocket_gateway_service.unsubscribe_user_from_all_tasks(user_id)
        except Exception as e:
            logger.error(f"User subscription cleanup failed: {e}")
        
        try:
            await manager.disconnect(user_id)
        except Exception as e:
            logger.error(f"Failed to disconnect user connection: {e}")

async def handle_client_message(user_id: str, message: Dict[str, Any]):
    """Process client message"""
    message_type = message.get("type")
    
    if message_type == "sync_subscriptions":
        # New idempotent subscription method
        project_ids = message.get("project_ids", [])
        # Sending message failedID, Let gateway service perform internal normalization
        channels = set(project_ids)
        
        stats = await websocket_gateway_service.sync_user_subscriptions(user_id, channels)
        
        response = WebSocketMessage.create_system_notification(
            "subscription_sync",
            "Subscription synchronized successfully",
            f"Added {stats['added']} / Removed {stats['removed']} / Unchanged {stats['unchanged']}",
            "success"
        )
        await manager.send_personal_message(response, user_id)
        
    elif message_type == "subscribe":
        # Subscribe topic (compatible with old version))
        topic = message.get("topic")
        if topic:
            manager.subscribe_to_topic(user_id, topic)
            response = WebSocketMessage.create_system_notification(
                "subscription",
                "Subscription successful",
                f"Topic subscribed successfully: {topic}",
                "success"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "subscribe_task":
        # Subscribe to subscription task progress (new version))
        task_id = message.get("task_id")
        if task_id:
            success = await websocket_gateway_service.subscribe_user_to_task(user_id, task_id)
            if success:
                response = WebSocketMessage.create_system_notification(
                    "task_subscription",
                    "Task subscription successful",
                    f"Task subscribed successfully {task_id} Progress updated for",
                    "success"
                )
            else:
                response = WebSocketMessage.create_error_notification(
                    "task_subscription_failed",
                    "Subscription task failed",
                    {"task_id": task_id}
                )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "unsubscribe":
        # Unsubscribe topic (compatible with old version))
        topic = message.get("topic")
        if topic:
            manager.unsubscribe_from_topic(user_id, topic)
            response = WebSocketMessage.create_system_notification(
                "unsubscription",
                "Unsubscription successful",
                f"Topic unsubscribed: {topic}",
                "info"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "unsubscribe_task":
        # Cancel subscription task progress (new version))
        task_id = message.get("task_id")
        if task_id:
            success = await websocket_gateway_service.unsubscribe_user_from_task(user_id, task_id)
            if success:
                response = WebSocketMessage.create_system_notification(
                    "task_unsubscription",
                    "Task unsubscribed successfully",
                    f"Task unsubscribed {task_id} Progress updated for",
                    "info"
                )
            else:
                response = WebSocketMessage.create_error_notification(
                    "task_unsubscription_failed",
                    "Failed to unsubscribe task",
                    {"task_id": task_id}
                )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "subscribe_many":
        # Bulk subscription task
        task_ids = message.get("channels", [])
        if task_ids:
            results = await websocket_gateway_service.subscribe_user_to_many_tasks(user_id, task_ids)
            response = WebSocketMessage.create_system_notification(
                "batch_subscription",
                "Task subscribe successful",
                f"Added new subscription: {len(results['added'])}, Already exists: {len(results['already_subscribed'])}",
                "success"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "unsubscribe_many":
        # Batch cancel subscription tasks
        task_ids = message.get("channels", [])
        if task_ids:
            results = await websocket_gateway_service.unsubscribe_user_from_many_tasks(user_id, task_ids)
            response = WebSocketMessage.create_system_notification(
                "batch_unsubscription",
                "Bulk unsubscribe complete",
                f"Removed subscription: {len(results['removed'])}, Not subscribed: {len(results['not_subscribed'])}",
                "success"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "sync_subscriptions":
        # Synchronize subscription set
        task_ids = message.get("channels", [])
        results = await websocket_gateway_service.sync_user_subscriptions(user_id, task_ids)
        response = WebSocketMessage.create_system_notification(
            "subscription_sync",
            "Subscription set synchronized",
            f"Added: {len(results['added'])}, Removed: {len(results['removed'])}, Unchanged: {len(results['unchanged'])}",
            "success"
        )
        await manager.send_personal_message(response, user_id)
    
    elif message_type == "ping":
        # Heartbeat detection
        response = {
            "type": "pong",
            "timestamp": WebSocketMessage.create_system_notification(
                "ping", "", "", "info"
            )["timestamp"]
        }
        await manager.send_personal_message(response, user_id)
        logger.debug(f"User {user_id} Heartbeat check - repliedpong")
    
    elif message_type == "get_status":
        # Get connection status
        gateway_status = await websocket_gateway_service.get_subscription_status(user_id)
        status = {
            "type": "status",
            "user_id": user_id,
            "connected": user_id in manager.active_connections,
            "subscriptions": list(manager.user_subscriptions.get(user_id, set())),
            "task_subscriptions": gateway_status["subscribed_tasks"],
            "total_connections": manager.get_connection_count(),
            "timestamp": WebSocketMessage.create_system_notification(
                "status", "", "", "info"
            )["timestamp"]
        }
        await manager.send_personal_message(status, user_id)
    
    else:
        # Unknown message type
        error_message = WebSocketMessage.create_error_notification(
            "unknown_message_type",
            "Unknown message type",
            {"message_type": message_type, "supported_types": ["subscribe", "subscribe_task", "unsubscribe", "unsubscribe_task", "ping", "get_status"]}
        )
        await manager.send_personal_message(error_message, user_id)

@router.get("/ws/status")
async def get_websocket_status():
    """RetrievedWebSocketService status"""
    return {
        "status": "running",
        "total_connections": manager.get_connection_count(),
        "topics": {
            topic: manager.get_topic_subscriber_count(topic)
            for topic in manager.topic_subscribers
        }
    }

@router.post("/ws/broadcast")
async def broadcast_message(message: Dict[str, Any]):
    """Broadcast message to all connected users"""
    try:
        await manager.broadcast(message)
        return {"status": "success", "message": "Directly pass in project"}
    except Exception as e:
        logger.error(f"Broadcasting failed: {e}")
        raise HTTPException(status_code=500, detail=f"Broadcasting failed: {e}")

@router.post("/ws/broadcast/{topic}")
async def broadcast_to_topic(topic: str, message: Dict[str, Any]):
    """Broadcast message to subscribers of specific topic"""
    try:
        await manager.broadcast_to_topic(message, topic)
        return {"status": "success", "message": f"Message broadcast to topic sent {topic} subscriber of"}
    except Exception as e:
        logger.error(f"Broadcast message to topic {topic} Failed: {e}")
        raise HTTPException(status_code=500, detail=f"Broadcasting failed: {e}")

@router.post("/ws/send/{user_id}")
async def send_to_user(user_id: str, message: Dict[str, Any]):
    """Send message to specific user"""
    try:
        await manager.send_personal_message(message, user_id)
        return {"status": "success", "message": f"Message has been sent to user {user_id}"}
    except Exception as e:
        logger.error(f"Send message to user {user_id} Failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk subscribe complete: {e}")