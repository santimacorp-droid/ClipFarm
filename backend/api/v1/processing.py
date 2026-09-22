"""
ProcessAPIRoute
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...services.processing_service import ProcessingService

router = APIRouter()


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingService:
    """Dependency to get processing service."""
    return ProcessingService(db)


@router.post("/projects/{project_id}/process")
async def process_project(
    project_id: str,
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Start processing project"""
    try:
        result = processing_service.process_project(project_id)
        return {
            "message": "Project processing has started",
            "project_id": project_id,
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Missing required file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/projects/{project_id}/processing-status")
async def get_processing_status(
    project_id: str,
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Get project processing status"""
    try:
        status = processing_service.get_processing_status(project_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/projects/{project_id}/process/step/{step_number}")
async def process_step(
    project_id: str,
    step_number: int,
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Process single step"""
    if step_number < 1 or step_number > 6:
        raise HTTPException(status_code=400, detail="Step number must be in1-6Between")
    
    try:
        # Here you can extend for handling a single step
        result = processing_service.process_project(project_id)
        return {
            "message": f"Step {step_number} Processing completed",
            "project_id": project_id,
            "step": step_number,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Step processing failed: {str(e)}")