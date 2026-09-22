"""
TaskRepository
Provide task-related data access operations
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from .base import BaseRepository
from ..models.task import Task, TaskStatus, TaskType

class TaskRepository(BaseRepository[Task]):
    """Task Repository class"""
    
    def __init__(self, db: Session):
        super().__init__(Task, db)
    
    def find_all(self, skip: int = 0, limit: int = 100, **filters) -> List[Task]:
        """
        Get all tasks, support filtering and pagination
        
        Args:
            skip: Skipped record count
            limit: Result count limit
            **filters: Filter criteria
            
        Returns:
            Task list
        """
        query = self.db.query(self.model)
        
        # Apply filter conditions
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.filter(getattr(self.model, key) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_project(self, project_id: str) -> List[Task]:
        """
        Get all tasks of a project
        
        Args:
            project_id: ProjectID
            
        Returns:
            Task list
        """
        return self.find_by(project_id=project_id)
    
    def get_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Get a list of tasks by state
        
        Args:
            status: Task status
            
        Returns:
            Task list
        """
        return self.find_by(status=status)
    
    def get_by_type(self, task_type: TaskType) -> List[Task]:
        """
        Get a list of tasks by task type
        
        Args:
            task_type: Task type
            
        Returns:
            Task list
        """
        return self.find_by(task_type=task_type)
    
    def get_by_project_and_status(self, project_id: str, status: TaskStatus) -> List[Task]:
        """
        Get a list of tasks by project and state
        
        Args:
            project_id: ProjectID
            status: Task status
            
        Returns:
            Task list
        """
        return self.find_by(project_id=project_id, status=status)
    
    def get_by_project_and_type(self, project_id: str, task_type: TaskType) -> List[Task]:
        """
        Get a list of tasks by project and task type
        
        Args:
            project_id: ProjectID
            task_type: Task type
            
        Returns:
            Task list
        """
        return self.find_by(project_id=project_id, task_type=task_type)
    
    def get_pending_tasks(self) -> List[Task]:
        """
        Get pending task
        
        Returns:
            Pending task list
        """
        return self.find_by(status=TaskStatus.PENDING)
    
    def get_running_tasks(self) -> List[Task]:
        """
        Get running tasks
        
        Returns:
            List of running tasks
        """
        return self.find_by(status=TaskStatus.RUNNING)
    
    def get_completed_tasks(self) -> List[Task]:
        """
        Get completed tasks
        
        Returns:
            List of completed tasks
        """
        return self.find_by(status=TaskStatus.COMPLETED)
    
    def get_failed_tasks(self) -> List[Task]:
        """
        Get failed tasks
        
        Returns:
            List of failed tasks
        """
        return self.find_by(status=TaskStatus.FAILED)
    
    def get_tasks_by_step(self, project_id: str, step: int) -> List[Task]:
        """
        Get tasks by processing step
        
        Args:
            project_id: ProjectID
            step: Processing steps
            
        Returns:
            Task list
        """
        return self.find_by(project_id=project_id, step=step)
    
    def get_next_pending_task(self) -> Optional[Task]:
        """
        Get next pending task
        
        Returns:
            Next pending task orNone
        """
        return self.db.query(self.model).filter(
            self.model.status == TaskStatus.PENDING
        ).order_by(asc(self.model.created_at)).first()
    
    def get_tasks_by_priority(self, priority: int) -> List[Task]:
        """
        Get task by priority
        
        Args:
            priority: Priority level
            
        Returns:
            Task list
        """
        return self.find_by(priority=priority)
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        """
        Update task status
        
        Args:
            task_id: TaskID
            status: New state
            
        Returns:
            Updated task instance or ...None
        """
        return self.update(task_id, status=status)
    
    def update_task_progress(self, task_id: str, progress: float) -> Optional[Task]:
        """
        Update task progress
        
        Args:
            task_id: TaskID
            progress: Progress percentage
            
        Returns:
            Updated task instance or ...None
        """
        return self.update(task_id, progress=progress)
    
    def update_task_result(self, task_id: str, result: dict) -> Optional[Task]:
        """
        Update task result
        
        Args:
            task_id: TaskID
            result: Task result
            
        Returns:
            Updated task instance or ...None
        """
        return self.update(task_id, result=result)
    
    def update_task_error(self, task_id: str, error_message: str) -> Optional[Task]:
        """
        Update task error info
        
        Args:
            task_id: TaskID
            error_message: Error message
            
        Returns:
            Updated task instance or ...None
        """
        return self.update(task_id, error_message=error_message, status=TaskStatus.FAILED)
    
    def get_tasks_statistics(self, project_id: str = None) -> dict:
        """
        Get task statistics
        
        Args:
            project_id: Project ID; if None is specified, count all projects
            
        Returns:
            Statistics dictionary
        """
        query = self.db.query(self.model)
        if project_id:
            query = query.filter(self.model.project_id == project_id)
        
        total_tasks = query.count()
        pending_tasks = query.filter(self.model.status == TaskStatus.PENDING).count()
        running_tasks = query.filter(self.model.status == TaskStatus.RUNNING).count()
        completed_tasks = query.filter(self.model.status == TaskStatus.COMPLETED).count()
        failed_tasks = query.filter(self.model.status == TaskStatus.FAILED).count()
        
        return {
            "total": total_tasks,
            "pending": pending_tasks,
            "running": running_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    
    def get_recent_tasks(self, limit: int = 10) -> List[Task]:
        """
        Recent tasks
        
        Args:
            limit: Return count limit
            
        Returns:
            Recent task list
        """
        return self.db.query(self.model).order_by(
            desc(self.model.created_at)
        ).limit(limit).all()
    
    def get_tasks_by_date_range(self, start_date, end_date, project_id: str = None) -> List[Task]:
        """
        Get tasks by date range
        
        Args:
            start_date: Start date
            end_date: End date
            project_id: Project ID; if None is specified, query all projects
            
        Returns:
            Task list
        """
        query = self.db.query(self.model).filter(
            self.model.created_at >= start_date,
            self.model.created_at <= end_date
        )
        
        if project_id:
            query = query.filter(self.model.project_id == project_id)
        
        return query.order_by(desc(self.model.created_at)).all()
    
    def get_long_running_tasks(self, max_duration_hours: int = 2) -> List[Task]:
        """
        Get long-running tasks
        
        Args:
            max_duration_hours: Maximum runtime (hours))
            
        Returns:
            List of long-running tasks
        """
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=max_duration_hours)
        
        return self.db.query(self.model).filter(
            self.model.status == TaskStatus.RUNNING,
            self.model.started_at <= cutoff_time
        ).all()
    
    def cleanup_old_tasks(self, days: int = 30) -> int:
        """
        Clean old tasks, including abnormal status tasks
        
        Args:
            days: Retention days
            
        Returns:
            Deleted task count
        """
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        long_running_cutoff = datetime.utcnow() - timedelta(hours=24)
        
        total_deleted = 0
        
        try:
            # 1. Clean up expired completed/failure tasks
            completed_tasks = self.db.query(self.model).filter(
                self.model.created_at < cutoff_date,
                self.model.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            ).delete(synchronize_session=False)
            
            total_deleted += completed_tasks
            logger.info(f"Cleaned up {completed_tasks} expired completed ones/Failed tasks")
            
            # 2. Fix long-running abnormal tasks
            long_running_tasks = self.db.query(self.model).filter(
                self.model.status == TaskStatus.RUNNING,
                self.model.created_at < long_running_cutoff
            ).all()
            
            fixed_count = 0
            for task in long_running_tasks:
                task.status = TaskStatus.FAILED
                task.error_message = "Task timeout; automatically marked as failure"
                task.updated_at = datetime.utcnow()
                fixed_count += 1
                logger.info(f"Fix long-running tasks: {task.id}")
            
            if fixed_count > 0:
                self.db.commit()
                logger.info(f"Fixed {fixed_count} long-running tasks")
            
            # Clean up orphaned tasks (tasks without corresponding projects)
            from ..models.project import Project
            all_project_ids = {p.id for p in self.db.query(Project).all()}
            orphaned_tasks = self.db.query(self.model).filter(
                ~self.model.project_id.in_(all_project_ids)
            ).all()
            
            orphaned_count = 0
            for task in orphaned_tasks:
                self.db.delete(task)
                orphaned_count += 1
                logger.info(f"Clean up orphaned tasks: {task.id}")
            
            if orphaned_count > 0:
                self.db.commit()
                logger.info(f"Cleaned up {orphaned_count} A standalone task")
            
            return total_deleted + fixed_count + orphaned_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Cleanup failed task: {e}")
            raise