"""
Pipeline controlAPI
Provide manual start/stop and query pipeline status functionality
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from ...core.database import get_db
from ...models.project import Project, ProjectStatus
from ...models.task import Task, TaskStatus
from ...services.auto_pipeline_service import auto_pipeline_service
from ...services.progress_update_service import progress_update_service
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/start/{project_id}")
async def start_pipeline(
    project_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually started project pipeline"""
    try:
        # Check if project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check project state
        if project.status == ProjectStatus.PROCESSING:
            return {"status": "skipped", "message": "Project already in progress"}
        
        if project.status == ProjectStatus.COMPLETED:
            return {"status": "skipped", "message": "Project completed"}
        
        # Check for running tasks
        running_task = db.query(Task).filter(
            Task.project_id == project_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).first()
        
        if running_task and running_task.status == TaskStatus.RUNNING:
            return {"status": "skipped", "message": "Project has running tasks"}
        
        # Start pipeline in background
        background_tasks.add_task(
            auto_pipeline_service.auto_start_pipeline,
            project_id
        )
        
        return {
            "status": "started",
            "message": "Started pipeline task submitted",
            "project_id": project_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Start pipeline failed: {str(e)}")

@router.post("/stop/{project_id}")
async def stop_pipeline(project_id: str, db: Session = Depends(get_db)):
    """Stop project pipeline"""
    try:
        # Check if project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Find running tasks
        running_tasks = db.query(Task).filter(
            Task.project_id == project_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).all()
        
        if not running_tasks:
            return {"status": "skipped", "message": "No running tasks"}
        
        # Stopped all running tasks
        stopped_count = 0
        for task in running_tasks:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.utcnow()
            
            # Stopped task notified via progress update service
            try:
                await progress_update_service.complete_task(
                    task_id=task.id,
                    error="Task manually stopped"
                )
            except Exception as e:
                logger.warning(f"Failed to notify task stop: {e}")
            
            stopped_count += 1
        
        # Update project state
        project.status = ProjectStatus.PENDING
        project.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "stopped",
            "message": f"Stopped {stopped_count} tasks",
            "project_id": project_id,
            "stopped_tasks": stopped_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stop pipeline failed: {str(e)}")

@router.post("/restart/{project_id}")
async def restart_pipeline(
    project_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Restart project pipeline"""
    try:
        # Stop existing pipeline first
        stop_result = await stop_pipeline(project_id, db)
        
        # Wait a moment to ensure stop completion
        import time
        time.sleep(2)
        
        # Restart pipeline
        start_result = await start_pipeline(project_id, background_tasks, db)
        
        return {
            "status": "restarted",
            "message": "Pipeline restarted",
            "project_id": project_id,
            "stop_result": stop_result,
            "start_result": start_result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restart pipeline failed: {str(e)}")

@router.get("/status/{project_id}")
async def get_pipeline_status(project_id: str, db: Session = Depends(get_db)):
    """Get project pipeline status"""
    try:
        # Check if project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get project task
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        
        # Get live progress info
        task_statuses = []
        for task in tasks:
            realtime_progress = progress_update_service.get_task_progress(task.id)
            
            task_info = {
                'id': task.id,
                'name': task.name,
                'status': task.status,
                'progress': task.progress,
                'current_step': task.current_step,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'updated_at': task.updated_at.isoformat() if task.updated_at else None
            }
            
            if realtime_progress:
                task_info.update({
                    'realtime_progress': realtime_progress['progress'],
                    'realtime_step': realtime_progress['current_step'],
                    'step_details': realtime_progress.get('step_details')
                })
            
            task_statuses.append(task_info)
        
        return {
            'project_id': project_id,
            'project_status': project.status,
            'tasks': task_statuses,
            'total_tasks': len(tasks),
            'running_tasks': len([t for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]),
            'completed_tasks': len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            'failed_tasks': len([t for t in tasks if t.status == TaskStatus.FAILED])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline status: {str(e)}")

@router.get("/overview")
async def get_pipeline_overview(db: Session = Depends(get_db)):
    """Get all pipeline summaries"""
    try:
        # Get all projects
        projects = db.query(Project).all()
        
        overview = {
            'total_projects': len(projects),
            'processing_projects': 0,
            'completed_projects': 0,
            'failed_projects': 0,
            'pending_projects': 0,
            'project_details': []
        }
        
        for project in projects:
            # Get project task statistics
            tasks = db.query(Task).filter(Task.project_id == project.id).all()
            
            project_info = {
                'id': project.id,
                'name': project.name,
                'status': project.status,
                'total_tasks': len(tasks),
                'running_tasks': len([t for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]),
                'completed_tasks': len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                'failed_tasks': len([t for t in tasks if t.status == TaskStatus.FAILED])
            }
            
            overview['project_details'].append(project_info)
            
            # Count project status
            if project.status == ProjectStatus.PROCESSING:
                overview['processing_projects'] += 1
            elif project.status == ProjectStatus.COMPLETED:
                overview['completed_projects'] += 1
            elif project.status == ProjectStatus.FAILED:
                overview['failed_projects'] += 1
            elif project.status == ProjectStatus.PENDING:
                overview['pending_projects'] += 1
        
        # Get automation service status
        auto_service_status = auto_pipeline_service.get_processing_status()
        overview['auto_service'] = auto_service_status
        
        return overview
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline summary: {str(e)}")

@router.post("/auto-start-all")
async def auto_start_all_pending_pipelines(background_tasks: BackgroundTasks):
    """Started all waiting pipelines in background"""
    try:
        # Started all waiting projects in background
        background_tasks.add_task(
            auto_pipeline_service.auto_start_all_pending_pipelines
        )
        
        return {
            "status": "started",
            "message": "Submitted tasks for automatic startup of all waiting pipelines"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-start failed: {str(e)}")
