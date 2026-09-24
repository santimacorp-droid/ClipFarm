#!/usr/bin/env python3
"""
Execute the real pipeline script following the original architecturePipelineAdapterAnd the original pipeline steps
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any

# Add project root directory toPythonpath
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.database import SessionLocal
from backend.models.project import Project, ProjectStatus
from backend.models.task import Task, TaskStatus
from backend.services.pipeline_adapter import create_pipeline_adapter_sync
import logging

# Setting logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def execute_real_pipeline(project_id: str):
    """Execute the real pipeline following the original architecture"""
    
    logger.info(f"Starting project execution {project_id} the actual pipeline")
    
    try:
        # Create database session
        db = SessionLocal()
        
        try:
            # Validate that the project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"project {project_id} does not exist")
            
            logger.info(f"Verifying project existence: {project.name}")
            
            # Creating task record
            task = Task(
                name=f"Real pipeline processing",
                description=f"Process project using the original architecture {project_id}",
                task_type="VIDEO_PROCESSING",
                project_id=project_id,
                status=TaskStatus.RUNNING,
                progress=0,
                current_step="initialization",
                total_steps=6
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            
            logger.info(f"Task record created: {task.id}")
            
            # Preparing file paths
            from backend.core.path_utils import get_project_directory
            data_root = get_project_directory(project_id)
            input_video_path = data_root / "raw" / "input.mp4"
            input_srt_path = data_root / "raw" / "input.srt"
            
            # Verifying file existence
            if not input_video_path.exists():
                raise FileNotFoundError(f"Video file does not exist: {input_video_path}")
            if not input_srt_path.exists():
                raise FileNotFoundError(f"Subtitle file does not exist: {input_srt_path}")
            
            logger.info(f"File path validation succeeded:")
            logger.info(f"  video: {input_video_path}")
            logger.info(f"  subtitles: {input_srt_path}")
            
            # createPipelineadapter
            pipeline_adapter = create_pipeline_adapter_sync(db, str(task.id), project_id)
            
            # Validate pipeline prerequisites
            logger.info("Validate pipeline prerequisites...")
            errors = pipeline_adapter.validate_pipeline_prerequisites()
            if errors:
                error_msg = "; ".join(errors)
                logger.error(f"Pipeline prerequisite validation failed: {error_msg}")
                raise ValueError(f"Pipeline prerequisite validation failed: {error_msg}")
            
            logger.info("Pipeline prerequisite validation passed")
            
            # Execute full pipeline processing
            logger.info("Begin executing full pipeline...")
            result = pipeline_adapter.process_project_sync(
                project_id=project_id,
                input_video_path=str(input_video_path),
                input_srt_path=str(input_srt_path)
            )
            
            # Checking processing results
            if result.get('status') == 'failed':
                error_msg = result.get('message', 'Processing failed')
                logger.error(f"Pipeline processing failed: {error_msg}")
                
                # Update task status to failure
                task.status = TaskStatus.FAILED
                task.error_message = error_msg
                db.commit()
                
                return {
                    "success": False,
                    "error": error_msg,
                    "result": result
                }
            else:
                # Processing succeeded
                logger.info("🎉 Pipeline processing succeeded! ")
                logger.info(f"Processing result: {result}")
                
                # Update task status to complete
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.current_step = "Processing complete"
                db.commit()
                
                return {
                    "success": True,
                    "result": result,
                    "message": "Pipeline processing complete"
                }
                
        finally:
            db.close()
            
    except Exception as e:
        error_msg = f"Pipeline execution failed: {str(e)}"
        logger.error(error_msg)
        
        # Attempting to update task status
        try:
            db = SessionLocal()
            task = db.query(Task).filter(Task.project_id == project_id).order_by(Task.created_at.desc()).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = error_msg
                db.commit()
            db.close()
        except Exception as db_error:
            logger.error(f"Updating task status failed: {db_error}")
        
        return {
            "success": False,
            "error": error_msg
        }

async def main():
    """main function"""
    if len(sys.argv) != 2:
        print("Usage method: python execute_real_pipeline.py <project_id>")
        sys.exit(1)
    
    project_id = sys.argv[1]
    
    result = await execute_real_pipeline(project_id)
    
    if result["success"]:
        print(f"✅ Pipeline execution successful! ")
        print(f"📊 result: {result['result']}")
    else:
        print(f"❌ Pipeline execution failed: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
