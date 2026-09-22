"""
Data cleanup task
Regularly clean up expired data in the database and file system
"""

import os
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from celery import current_task, shared_task

from ..core.celery_app import celery_app
from ..core.database import SessionLocal
from ..models.task import Task, TaskStatus
from ..models.project import Project, ProjectStatus
from ..models.clip import Clip
from ..models.collection import Collection
from ..repositories.task_repository import TaskRepository
from ..repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='backend.tasks.data_cleanup.cleanup_expired_data')
def cleanup_expired_data(self, days: int = 30) -> Dict[str, Any]:
    """
    Clean up expired data
    
    Args:
        days: Retention days, default 30 days
        
    Returns:
        Cleanup result
    """
    logger.info(f"Starting cleanup of expired data, retaining days: {days}")
    
    try:
        # Create database session
        db = SessionLocal()
        
        try:
            cleanup_results = {
                'timestamp': datetime.utcnow().isoformat(),
                'days': days,
                'tasks_cleaned': 0,
                'projects_cleaned': 0,
                'files_cleaned': 0,
                'errors': []
            }
            
            # Clean up expired tasks
            try:
                task_repo = TaskRepository(db)
                tasks_cleaned = task_repo.cleanup_old_tasks(days)
                cleanup_results['tasks_cleaned'] = tasks_cleaned
                logger.info(f"Cleaned up {tasks_cleaned} expired tasks")
            except Exception as e:
                error_msg = f"Task cleanup failed: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            # 2. Clean up expired projects
            try:
                projects_cleaned = _cleanup_expired_projects(db, days)
                cleanup_results['projects_cleaned'] = projects_cleaned
                logger.info(f"Cleaned up {projects_cleaned} expired projects")
            except Exception as e:
                error_msg = f"Failed to purge project: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            # Clean up orphaned files
            try:
                files_cleaned = _cleanup_orphaned_files()
                cleanup_results['files_cleaned'] = files_cleaned
                logger.info(f"Cleaned up {files_cleaned} orphaned files")
            except Exception as e:
                error_msg = f"File cleanup failed: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            # 4. Clean temporary files
            try:
                temp_files_cleaned = _cleanup_temp_files()
                cleanup_results['temp_files_cleaned'] = temp_files_cleaned
                logger.info(f"Cleaned up {temp_files_cleaned} temporary files")
            except Exception as e:
                error_msg = f"Failed to clean temporary files: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            cleanup_results['success'] = len(cleanup_results['errors']) == 0
            cleanup_results['total_cleaned'] = (
                cleanup_results['tasks_cleaned'] + 
                cleanup_results['projects_cleaned'] + 
                cleanup_results['files_cleaned'] +
                cleanup_results.get('temp_files_cleaned', 0)
            )
            
            logger.info(f"Data cleanup complete, total cleaned up {cleanup_results['total_cleaned']} items of data")
            return cleanup_results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Cleanup of expired data failed, error: {e}")
        raise


def _cleanup_expired_projects(db: SessionLocal, days: int) -> int:
    """Clean up expired projects"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Find completed projects that have expired
    expired_projects = db.query(Project).filter(
        Project.status == ProjectStatus.COMPLETED,
        Project.updated_at < cutoff_date
    ).all()
    
    cleaned_count = 0
    for project in expired_projects:
        try:
            # Delete project-related data
            _delete_project_data(db, project.id)
            cleaned_count += 1
            logger.info(f"Clean up expired projects: {project.id}")
        except Exception as e:
            logger.error(f"Cleanup project {project.id} Failed: {e}")
    
    return cleaned_count


def _delete_project_data(db: SessionLocal, project_id: str):
    """Delete project data"""
    # Delete related tasks
    db.query(Task).filter(Task.project_id == project_id).delete()
    
    # Delete related slices
    db.query(Clip).filter(Clip.project_id == project_id).delete()
    
    # Delete related collections
    db.query(Collection).filter(Collection.project_id == project_id).delete()
    
    # Delete project record
    db.query(Project).filter(Project.id == project_id).delete()
    
    # Delete project files
    project_dir = Path(f"data/projects/{project_id}")
    if project_dir.exists():
        shutil.rmtree(project_dir)
    
    # Clean up progress data
    try:
        from ..services.simple_progress import clear_progress
        clear_progress(project_id)
    except Exception as e:
        logger.warning(f"Failed to clean progress data: {e}")
    
    db.commit()


def _cleanup_orphaned_files() -> int:
    """Purge orphaned files"""
    cleaned_count = 0
    
    try:
        # Get project ID in database
        db = SessionLocal()
        try:
            db_projects = {p.id for p in db.query(Project).all()}
        finally:
            db.close()
        
        # Clean orphaned project directory
        projects_dir = Path("data/projects")
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir() and project_dir.name not in db_projects:
                    if not project_dir.name.startswith('.'):
                        shutil.rmtree(project_dir)
                        cleaned_count += 1
                        logger.info(f"Clean up orphaned project directory: {project_dir.name}")
        
        # Clean up orphaned output files
        output_dir = Path("data/output")
        if output_dir.exists():
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    # Check if the file belongs to an existing project
                    file_name = file_path.name
                    is_orphaned = True
                    
                    for project_id in db_projects:
                        if project_id in file_name:
                            is_orphaned = False
                            break
                    
                    if is_orphaned:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"Clean up orphaned output files: {file_path}")
        
    except Exception as e:
        logger.error(f"Failed to clean orphaned files: {e}")
    
    return cleaned_count


def _cleanup_temp_files() -> int:
    """Clean up temporary files"""
    cleaned_count = 0
    
    try:
        temp_dir = Path("data/temp")
        if temp_dir.exists():
            for file_path in temp_dir.iterdir():
                if file_path.is_file():
                    # Check if the file is older than one hour
                    file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_age > timedelta(hours=1):
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"Clean up temporary files: {file_path}")
        
        # Clean up processed intermediate files and chunk cache
        from ..core.path_utils import get_data_directory
        projects_dir = get_data_directory() / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    processing_dir = project_dir / "processing"
                    if processing_dir.exists():
                        for file_path in processing_dir.iterdir():
                            if file_path.is_file():
                                file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                                if file_age > timedelta(hours=24):
                                    file_path.unlink()
                                    cleaned_count += 1
                                    logger.info(f"Clean up processing intermediate files: {file_path}")
                    
                    # Clean up intermediate chunk directories for completed steps
                    meta_dir = project_dir / "output" / "metadata"
                    for chunk_dir_name in ["step1_srt_chunks", "step2_timeline_chunks", "step2_llm_raw_output"]:
                        chunk_folder = meta_dir / chunk_dir_name
                        if chunk_folder.exists() and chunk_folder.is_dir():
                            for f in chunk_folder.glob("*.json"):
                                f_age = datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)
                                if f_age > timedelta(hours=48):
                                    f.unlink(missing_ok=True)
                                    cleaned_count += 1
                            for f in chunk_folder.glob("*.txt"):
                                f_age = datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)
                                if f_age > timedelta(hours=48):
                                    f.unlink(missing_ok=True)
                                    cleaned_count += 1
        
    except Exception as e:
        logger.error(f"Failed to clean temporary files: {e}")
    
    return cleaned_count


@shared_task(bind=True, name='backend.tasks.data_cleanup.check_data_consistency')
def check_data_consistency(self) -> Dict[str, Any]:
    """
    Consistency check result
    
    Returns:
        Consistency check results
    """
    logger.info("Beginning data consistency check")
    
    try:
        # Create database session
        db = SessionLocal()
        
        try:
            issues = []
            
            # Check project data consistency
            db_projects = {p.id for p in db.query(Project).all()}
            fs_projects = set()
            
            projects_dir = Path("data/projects")
            if projects_dir.exists():
                for project_dir in projects_dir.iterdir():
                    if project_dir.is_dir() and not project_dir.name.startswith('.'):
                        fs_projects.add(project_dir.name)
            
            # Check for orphaned files
            orphaned_files = fs_projects - db_projects
            if orphaned_files:
                issues.append({
                    "type": "orphaned_files",
                    "count": len(orphaned_files),
                    "details": list(orphaned_files)
                })
            
            # Check for missing files
            missing_files = db_projects - fs_projects
            if missing_files:
                issues.append({
                    "type": "missing_files",
                    "count": len(missing_files),
                    "details": list(missing_files)
                })
            
            # Check task data consistency
            orphaned_tasks = db.query(Task).filter(
                ~Task.project_id.in_(db_projects)
            ).count()
            
            if orphaned_tasks > 0:
                issues.append({
                    "type": "orphaned_tasks",
                    "count": orphaned_tasks,
                    "details": []
                })
            
            # Check slice data consistency
            orphaned_clips = db.query(Clip).filter(
                ~Clip.project_id.in_(db_projects)
            ).count()
            
            if orphaned_clips > 0:
                issues.append({
                    "type": "orphaned_clips",
                    "count": orphaned_clips,
                    "details": []
                })
            
            # Check assembly data consistency
            orphaned_collections = db.query(Collection).filter(
                ~Collection.project_id.in_(db_projects)
            ).count()
            
            if orphaned_collections > 0:
                issues.append({
                    "type": "orphaned_collections",
                    "count": orphaned_collections,
                    "details": []
                })
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'total_issues': len(issues),
                'issues': issues,
                'status': 'healthy' if len(issues) == 0 else 'unhealthy'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Data consistency check failed, error: {e}")
        raise


@shared_task(bind=True, name='backend.tasks.data_cleanup.cleanup_orphaned_data')
def cleanup_orphaned_data(self) -> Dict[str, Any]:
    """
    Purge orphaned data
    
    Returns:
        Cleanup result
    """
    logger.info("Start cleaning orphaned data")
    
    try:
        # Create database session
        db = SessionLocal()
        
        try:
            cleanup_results = {
                'timestamp': datetime.utcnow().isoformat(),
                'orphaned_tasks_cleaned': 0,
                'orphaned_clips_cleaned': 0,
                'orphaned_collections_cleaned': 0,
                'orphaned_files_cleaned': 0
            }
            
            # Get all project IDs
            db_projects = {p.id for p in db.query(Project).all()}
            
            # Clean up orphaned tasks
            orphaned_tasks = db.query(Task).filter(
                ~Task.project_id.in_(db_projects)
            ).all()
            
            for task in orphaned_tasks:
                db.delete(task)
                cleanup_results['orphaned_tasks_cleaned'] += 1
                logger.info(f"Purge orphaned tasks: {task.id}")
            
            # 2. Clean orphaned slices
            orphaned_clips = db.query(Clip).filter(
                ~Clip.project_id.in_(db_projects)
            ).all()
            
            for clip in orphaned_clips:
                db.delete(clip)
                cleanup_results['orphaned_clips_cleaned'] += 1
                logger.info(f"Clean up orphaned slices: {clip.id}")
            
            # 3. Clean up orphaned assemblies
            orphaned_collections = db.query(Collection).filter(
                ~Collection.project_id.in_(db_projects)
            ).all()
            
            for collection in orphaned_collections:
                db.delete(collection)
                cleanup_results['orphaned_collections_cleaned'] += 1
                logger.info(f"Clean up orphaned collections: {collection.id}")
            
            # 4. Clean orphaned files
            cleanup_results['orphaned_files_cleaned'] = _cleanup_orphaned_files()
            
            db.commit()
            
            total_cleaned = (
                cleanup_results['orphaned_tasks_cleaned'] +
                cleanup_results['orphaned_clips_cleaned'] +
                cleanup_results['orphaned_collections_cleaned'] +
                cleanup_results['orphaned_files_cleaned']
            )
            
            cleanup_results['total_cleaned'] = total_cleaned
            cleanup_results['success'] = True
            
            logger.info(f"Orphaned data cleanup complete, total cleaned up {total_cleaned} items of data")
            return cleanup_results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Orphan cleanup failed, error: {e}")
        raise
