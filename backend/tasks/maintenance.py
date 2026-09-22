"""
Maintenance task
"""

import os
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from celery import current_task, shared_task

from ..core.celery_app import celery_app
from ..core.database import SessionLocal
from ..models.task import Task, TaskStatus
from ..models.project import Project, ProjectStatus
from ..repositories.task_repository import TaskRepository
from ..repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='backend.tasks.maintenance.cleanup_expired_tasks')
def cleanup_expired_tasks(self, days: int = 7) -> Dict[str, Any]:
    """
    Clean expired tasks
    
    Args:
        days: Expiration days, default 7 days
        
    Returns:
        Cleanup result
    """
    logger.info(f"Starting cleanup of expired tasks, expiration days: {days}")
    
    try:
        # Creating database session
        db = SessionLocal()
        
        try:
            task_repo = TaskRepository(db)
            
            # Compute expiration time
            expired_time = datetime.utcnow() - timedelta(days=days)
            
            # Find expired tasks
            expired_tasks = db.query(Task).filter(
                Task.created_at < expired_time,
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            ).all()
            
            cleaned_count = 0
            
            for task in expired_tasks:
                try:
                    # Deleting task-related files
                    if task.result and isinstance(task.result, dict):
                        # Add file cleanup logic here
                        pass
                    
                    # Delete task records
                    task_repo.delete(task.id)
                    cleaned_count += 1
                    
                    logger.info(f"Expired tasks cleaned up successfully: {task.id}")
                    
                except Exception as e:
                    logger.error(f"Clean failed tasks: {task.id}, Error: {e}")
            
            logger.info(f"Cleanup of expired tasks complete, cleaned up: {count} {cleaned_count} tasks")
            return {
                'success': True,
                'cleaned_count': cleaned_count,
                'expired_time': expired_time.isoformat(),
                'message': f'Cleanup successful {cleaned_count} expired tasks'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to clean up expired tasks, error: {e}: {e}")
        raise


@shared_task(bind=True, name='backend.tasks.maintenance.health_check')
def health_check(self) -> Dict[str, Any]:
    """
    System health check
    
    Returns:
        Health check results
    """
    logger.info("Starting system health check")
    
    try:
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy',
            'checks': {}
        }
        
        # Checking database connection
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
            health_status['checks']['database'] = {'status': 'healthy', 'message': 'Database connection is normal'}
        except Exception as e:
            health_status['checks']['database'] = {'status': 'unhealthy', 'message': f'Database connection failed: {e}'}
            health_status['status'] = 'unhealthy'
        
        # Checking Redis connection
        try:
            import redis
            r = redis.Redis.from_url('redis://localhost:6379/0')
            r.ping()
            health_status['checks']['redis'] = {'status': 'healthy', 'message': 'RedisConnection established'}
        except Exception as e:
            health_status['checks']['redis'] = {'status': 'unhealthy', 'message': f'RedisConnection failed: {e}'}
            health_status['status'] = 'unhealthy'
        
        # Check disk space
        try:
            import psutil
            disk_usage = psutil.disk_usage('/')
            disk_percent = disk_usage.percent
            if disk_percent < 90:
                health_status['checks']['disk'] = {'status': 'healthy', 'message': f'Disk usage rate: {disk_percent}%'}
            else:
                health_status['checks']['disk'] = {'status': 'warning', 'message': f'Disk usage too high: {disk_percent}%'}
        except Exception as e:
            health_status['checks']['disk'] = {'status': 'unknown', 'message': f'Cannot check disk status: {e}'}
        
        # Check memory usage
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            if memory_percent < 80:
                health_status['checks']['memory'] = {'status': 'healthy', 'message': f'Memory usage rate: {memory_percent}%'}
            else:
                health_status['checks']['memory'] = {'status': 'warning', 'message': f'Memory usage too high: {memory_percent}%'}
        except Exception as e:
            health_status['checks']['memory'] = {'status': 'unknown', 'message': f'Cannot check memory status: {e}'}
        
        logger.info(f"System health check completed, status: {status}: {health_status['status']}")
        return health_status
        
    except Exception as e:
        logger.error(f"System health check failed, error: {e}: {e}")
        raise


@shared_task(bind=True, name='backend.tasks.maintenance.backup_project_data')
def backup_project_data(self, project_id: str, backup_path: str = None) -> Dict[str, Any]:
    """
    Backing up project data...
    
    Args:
        project_id: ProjectID
        backup_path: Backup path
        
    Returns:
        Backup result
    """
    logger.info(f"Starting backup of project data: {project_id}")
    
    try:
        # Creating database session
        db = SessionLocal()
        
        try:
            project_repo = ProjectRepository(db)
            project = project_repo.get_by_id(project_id)
            
            if not project:
                raise ValueError(f"Project does not exist: {project_id}")
            
            # Generate backup path
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"data/backups/{project_id}_{timestamp}"
            
            backup_dir = Path(backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Back up project directory
            project_dir = Path(f"data/projects/{project_id}")
            if project_dir.exists():
                backup_project_dir = backup_dir / "project_files"
                shutil.copytree(project_dir, backup_project_dir, dirs_exist_ok=True)
            
            # Backing up database records
            project_data = {
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'status': project.status.value,
                    'created_at': project.created_at.isoformat(),
                    'updated_at': project.updated_at.isoformat()
                },
                'tasks': [],
                'clips': [],
                'collections': []
            }
            
            # Back up task data
            tasks = db.query(Task).filter(Task.project_id == project_id).all()
            for task in tasks:
                project_data['tasks'].append({
                    'id': task.id,
                    'name': task.name,
                    'status': task.status.value,
                    'task_type': task.task_type.value,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': task.updated_at.isoformat()
                })
            
            # Save backup data
            import json
            backup_file = backup_dir / "project_data.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Project data backup complete: {project_id} -> {backup_path}")
            return {
                'success': True,
                'project_id': project_id,
                'backup_path': str(backup_path),
                'backup_size': sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()),
                'message': 'Project data backup successful'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Project data backup failed: {project_id}, Error: {e}")
        raise