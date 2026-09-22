"""
Concurrency control manager
Concurrency task and resource management
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """Task state"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """Task info"""
    task_id: str
    name: str
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)


class ResourceLimiter:
    """Resource quota"""
    
    def __init__(self, max_concurrent: int, resource_name: str):
        self.max_concurrent = max_concurrent
        self.resource_name = resource_name
        self.current_usage = 0
        self.waiting_queue = asyncio.Queue()
        self.lock = asyncio.Lock()
    
    async def acquire(self, task_id: str) -> bool:
        """Get resource"""
        
        async with self.lock:
            if self.current_usage < self.max_concurrent:
                self.current_usage += 1
                logger.debug(f"Task {task_id} Take {self.resource_name} Resources, current usage: {self.current_usage}/{self.max_concurrent}")
                return True
            else:
                logger.debug(f"Task {task_id} Wait {self.resource_name} Resource")
                await self.waiting_queue.put(task_id)
                return False
    
    async def release(self, task_id: str):
        """Release resources"""
        
        async with self.lock:
            if self.current_usage > 0:
                self.current_usage -= 1
                logger.debug(f"Task {task_id} Free {self.resource_name} Resources, current usage: {self.current_usage}/{self.max_concurrent}")
                
                # Notify the next when there are pending tasks
                if not self.waiting_queue.empty():
                    next_task_id = await self.waiting_queue.get()
                    logger.debug(f"Notify waiting tasks {next_task_id} Fetch {self.resource_name} Resource")
    
    def get_status(self) -> Dict[str, Any]:
        """Get resource status"""
        
        return {
            "resource_name": self.resource_name,
            "max_concurrent": self.max_concurrent,
            "current_usage": self.current_usage,
            "waiting_count": self.waiting_queue.qsize(),
            "utilization": self.current_usage / self.max_concurrent * 100
        }


class ConcurrencyManager:
    """Concurrency manager"""
    
    def __init__(self):
        self.resource_limiters: Dict[str, ResourceLimiter] = {}
        self.active_tasks: Dict[str, TaskInfo] = {}
        self.task_history: List[TaskInfo] = []
        self.task_counter = 0
        self.lock = asyncio.Lock()
        
        # Default resource limits
        self._setup_default_limits()
    
    def _setup_default_limits(self):
        """Set default resource limits"""
        
        # File upload limits
        self.add_resource_limiter("file_upload", 3)
        
        # Video processing limits
        self.add_resource_limiter("video_processing", 2)
        
        # AI processing limit
        self.add_resource_limiter("ai_processing", 4)
        
        # Database operation limits
        self.add_resource_limiter("database", 10)
        
        # Network request limits
        self.add_resource_limiter("network", 5)
    
    def add_resource_limiter(self, resource_name: str, max_concurrent: int):
        """Add resource limiter"""
        
        self.resource_limiters[resource_name] = ResourceLimiter(max_concurrent, resource_name)
        logger.info(f"Add resource limiter: {resource_name}, Maximum concurrency: {max_concurrent}")
    
    def _generate_task_id(self) -> str:
        """Generate taskID"""
        
        self.task_counter += 1
        return f"task_{self.task_counter}_{int(time.time())}"
    
    async def submit_task(
        self,
        name: str,
        coro: Callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        required_resources: List[str] = None,
        *args,
        **kwargs
    ) -> str:
        """Submit task"""
        
        task_id = self._generate_task_id()
        
        # Create task information
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            priority=priority,
            created_at=datetime.now()
        )
        
        async with self.lock:
            self.active_tasks[task_id] = task_info
        
        # Create and start tasks
        asyncio.create_task(self._execute_task(task_id, coro, required_resources or [], *args, **kwargs))
        
        logger.info(f"Submit task: {task_id}, Name: {name}, Priority: {priority.value}")
        
        return task_id
    
    async def _execute_task(
        self,
        task_id: str,
        coro: Callable,
        required_resources: List[str],
        *args,
        **kwargs
    ):
        """Execute task"""
        
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            return
        
        # Get required resources
        acquired_resources = []
        try:
            # Get resources by priority
            for resource_name in required_resources:
                if resource_name in self.resource_limiters:
                    limiter = self.resource_limiters[resource_name]
                    acquired = await limiter.acquire(task_id)
                    if acquired:
                        acquired_resources.append(resource_name)
                    else:
                        # Wait if unable to obtain a resource
                        await self._wait_for_resource(task_id, resource_name)
                        acquired_resources.append(resource_name)
            
            # Update task status
            task_info.status = TaskStatus.RUNNING
            task_info.started_at = datetime.now()
            
            # Execute task
            if asyncio.iscoroutinefunction(coro):
                result = await coro(*args, **kwargs)
            else:
                result = coro(*args, **kwargs)
            
            # Task completed
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now()
            task_info.result = result
            
            logger.info(f"Task completed: {task_id}, Elapsed time: {(task_info.completed_at - task_info.started_at).total_seconds():.2f}seconds")
            
        except Exception as e:
            # Task failed
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now()
            task_info.error = str(e)
            
            logger.error(f"Task failed: {task_id}, Error: {e}")
        
        finally:
            # Release resources
            for resource_name in acquired_resources:
                if resource_name in self.resource_limiters:
                    await self.resource_limiters[resource_name].release(task_id)
            
            # Move to historical record
            async with self.lock:
                if task_id in self.active_tasks:
                    self.task_history.append(self.active_tasks[task_id])
                    del self.active_tasks[task_id]
    
    async def _wait_for_resource(self, task_id: str, resource_name: str):
        """Wait for resources available"""
        
        if resource_name not in self.resource_limiters:
            return
        
        limiter = self.resource_limiters[resource_name]
        
        # Wait for resources available
        while True:
            async with limiter.lock:
                if limiter.current_usage < limiter.max_concurrent:
                    limiter.current_usage += 1
                    break
            
            # Retry after waiting briefly
            await asyncio.sleep(0.1)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel task"""
        
        async with self.lock:
            task_info = self.active_tasks.get(task_id)
            if not task_info:
                return False
            
            task_info.status = TaskStatus.CANCELLED
            task_info.completed_at = datetime.now()
            
            # Move to historical record
            self.task_history.append(task_info)
            del self.active_tasks[task_id]
        
        logger.info(f"Cancel task: {task_id}")
        return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        
        # Check active tasks
        task_info = self.active_tasks.get(task_id)
        if task_info:
            return self._task_info_to_dict(task_info)
        
        # Check historical tasks
        for task_info in self.task_history:
            if task_info.task_id == task_id:
                return self._task_info_to_dict(task_info)
        
        return None
    
    def _task_info_to_dict(self, task_info: TaskInfo) -> Dict[str, Any]:
        """Convert task information to dictionary"""
        
        result = {
            "task_id": task_info.task_id,
            "name": task_info.name,
            "priority": task_info.priority.value,
            "status": task_info.status.value,
            "created_at": task_info.created_at.isoformat(),
            "resource_usage": task_info.resource_usage
        }
        
        if task_info.started_at:
            result["started_at"] = task_info.started_at.isoformat()
        
        if task_info.completed_at:
            result["completed_at"] = task_info.completed_at.isoformat()
            
            # Calculate execution time
            if task_info.started_at:
                execution_time = (task_info.completed_at - task_info.started_at).total_seconds()
                result["execution_time"] = execution_time
        
        if task_info.error:
            result["error"] = task_info.error
        
        if task_info.result is not None:
            result["result"] = task_info.result
        
        return result
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get active task list"""
        
        return [self._task_info_to_dict(task_info) for task_info in self.active_tasks.values()]
    
    def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get task history"""
        
        recent_tasks = self.task_history[-limit:] if self.task_history else []
        return [self._task_info_to_dict(task_info) for task_info in recent_tasks]
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get resource status"""
        
        status = {}
        for resource_name, limiter in self.resource_limiters.items():
            status[resource_name] = limiter.get_status()
        
        return status
    
    def get_system_load(self) -> Dict[str, Any]:
        """Get system load"""
        
        active_count = len(self.active_tasks)
        total_waiting = sum(limiter.waiting_queue.qsize() for limiter in self.resource_limiters.values())
        
        # Calculate resource utilization
        resource_utilization = {}
        for resource_name, limiter in self.resource_limiters.items():
            resource_utilization[resource_name] = limiter.get_status()["utilization"]
        
        return {
            "active_tasks": active_count,
            "total_waiting": total_waiting,
            "resource_utilization": resource_utilization,
            "timestamp": datetime.now().isoformat()
        }
    
    def cleanup_old_history(self, max_age_hours: int = 24):
        """Clean up old historical records"""
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        # Filter historical records
        self.task_history = [
            task_info for task_info in self.task_history
            if task_info.created_at >= cutoff_time
        ]
        
        logger.info(f"Clean up task history, retain the most recent {max_age_hours} Hour's data")


# Global concurrency manager instance
concurrency_manager = ConcurrencyManager()


# Concurrency control decorator
def limit_concurrency(resource_name: str, priority: TaskPriority = TaskPriority.NORMAL):
    """Concurrency control decorator"""
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            task_id = await concurrency_manager.submit_task(
                name=func.__name__,
                coro=func,
                priority=priority,
                required_resources=[resource_name],
                *args,
                **kwargs
            )
            
            # Wait for task completion
            while True:
                status = concurrency_manager.get_task_status(task_id)
                if status and status["status"] in ["completed", "failed", "cancelled"]:
                    if status["status"] == "failed" and "error" in status:
                        raise Exception(status["error"])
                    return status.get("result")
                
                await asyncio.sleep(0.1)
        
        def sync_wrapper(*args, **kwargs):
            # Create asynchronous wrapper for synchronous functions
            async def async_func():
                return func(*args, **kwargs)
            
            return asyncio.run(async_wrapper())
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
