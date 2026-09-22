"""
Simplified progressAPI - Provide progress snapshot query interface
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from backend.services.simple_progress import get_multiple_progress_snapshots, get_progress_snapshot
from backend.core.progress_tracker import get_progress, get_all_progress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simple-progress", tags=["simple-progress"])


@router.get("/progress/{project_id}")
def get_project_progress(project_id: str):
    """Returns granular progress for a specific project."""
    progress = get_progress(project_id)
    if not progress:
        return {"status": "unknown", "overall_percent": 0}
    return progress


@router.get("/progress")
def get_all_projects_progress():
    """Returns progress snapshot for all active projects."""
    return {"projects": get_all_progress()}


@router.get("/snapshot")
def get_progress_snapshots(project_ids: List[str] = Query(..., description="Project ID List")):
    """
    Batch retrieve project progress snapshots
    
    Args:
        project_ids: Project ID List
        
    Returns:
        Progress snapshot list
    """
    try:
        if not project_ids:
            return []
            
        snapshots = get_multiple_progress_snapshots(project_ids)
        existing_pids = {s.get("project_id") for s in snapshots if s.get("project_id")}
        import time as _time
        for pid in project_ids:
            if pid not in existing_pids:
                t_state = get_progress(pid)
                if t_state:
                    synthetic_snap = {
                        "project_id": pid,
                        "stage": "ANALYZE" if t_state.get("current_step", 0) >= 2 else "INGEST",
                        "percent": int(t_state.get("overall_percent", 0)),
                        "message": t_state.get("substep") or t_state.get("step_name", ""),
                        "ts": int(_time.time())
                    }
                    synthetic_snap.update(t_state)
                    snapshots.append(synthetic_snap)

        # Enrich snapshots with in-memory granular tracker state if active
        for snap in snapshots:
            pid = snap.get("project_id")
            if pid:
                t_state = get_progress(pid)
                if t_state:
                    snap.update(t_state)
        logger.info(f"Get progress snapshot: {len(snapshots)} projects")
        return snapshots
        
    except Exception as e:
        logger.error(f"Failed to retrieve progress snapshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve progress snapshot: {str(e)}")


@router.get("/snapshot/{project_id}")
def get_single_progress_snapshot(project_id: str):
    """
    Retrieve single project progress snapshot
    
    Args:
        project_id: ProjectID
        
    Returns:
        Progress snapshot data
    """
    try:
        snapshot = get_progress_snapshot(project_id)
        if snapshot is None:
            # Return default status
            snapshot = {
                "project_id": project_id,
                "stage": "INGEST",
                "percent": 0,
                "message": "Waiting to start",
                "ts": 0
            }
        
        # Enrich with granular tracker state if active
        t_state = get_progress(project_id)
        if t_state:
            snapshot.update(t_state)
            
        return snapshot
        
    except Exception as e:
        logger.error(f"Retrieving project progress snapshot failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieving project progress snapshot failed: {str(e)}")


@router.get("/stages")
def get_available_stages():
    """
    Retrieve available processing phase information
    
    Returns:
        Phase configuration information
    """
    from backend.services.simple_progress import STAGES, STAGE_NAMES
    
    stages_info = []
    for stage, weight in STAGES:
        stages_info.append({
            "stage": stage,
            "weight": weight,
            "display_name": STAGE_NAMES.get(stage, stage)
        })
    
    return {
        "stages": stages_info,
        "total_weight": sum(weight for _, weight in STAGES)
    }
