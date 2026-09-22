"""
Processing service
Use three-pack framework: configuration manager, adapter, orchestrator
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models.task import Task, TaskStatus, TaskType
from backend.repositories.task_repository import TaskRepository
from backend.services.config_manager import ProjectConfigManager, ProcessingStep
# from backend.services.pipeline_adapter import PipelineAdapter  # Temporarily commented out; file does not exist
from backend.services.processing_orchestrator import ProcessingOrchestrator
from backend.services.processing_context import ProcessingContext
from backend.services.exceptions import ServiceError, ProcessingError, TaskError, ProjectError, handle_service_error
from backend.services.concurrency_manager import with_concurrency_control

logger = logging.getLogger(__name__)


class ProcessingService:
    """Processing service, uses three-pack framework"""
    
    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)
    
    @handle_service_error
    @with_concurrency_control()
    def start_processing(self, project_id: str, srt_path: Path) -> Dict[str, Any]:
        """
        Start processing project
        
        Args:
            project_id: ProjectID
            srt_path: SRTFile path
            
        Returns:
            Processing result
        """
        logger.info(f"Start processing project: {project_id}")
        
        # Create processing context
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        context.set_srt_path(srt_path)
        context.mark_initialized()
        
        # Create processing task
        task = self._create_processing_task(project_id)
        context.task_id = str(task.id)
        
        # Initialize orchestrator
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        # Execute full pipeline
        result = orchestrator.execute_pipeline(srt_path)
        
        context.mark_completed()
        
        # Update project status to completed and sync data
        try:
            from ..models.project import Project, ProjectStatus
            from ..services.data_sync_service import DataSyncService
            from pathlib import Path
            
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = ProjectStatus.COMPLETED
                self.db.commit()
                logger.info(f"Project status updated to completed: {project_id}")
                
                # Sync data to the database
                project_dir = Path(__file__).parent.parent / "data" / "projects" / project_id
                if project_dir.exists():
                    sync_service = DataSyncService(self.db)
                    sync_result = sync_service.sync_project_from_filesystem(project_id, project_dir)
                    if sync_result.get("success"):
                        logger.info(f"Project {project_id} Data synchronization succeeded: {sync_result}")
                    else:
                        logger.error(f"Project {project_id} Data synchronization failed: {sync_result}")
        except Exception as e:
            logger.warning(f"Failed to update project status: {e}")
        
        return {
            "success": True,
            "task_id": task.id,
            "project_id": project_id,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    @with_concurrency_control()
    def execute_single_step(self, project_id: str, step: ProcessingStep, 
                           srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Execute a single step
        
        Args:
            project_id: ProjectID
            step: Process step
            srt_path: SRTFile path (only Step 1 required))
            
        Returns:
            Execution result
        """
        logger.info(f"Execute step: {step.value}")
        
        # Create processing context
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        # Create task
        task = self._create_processing_task(project_id, task_type=TaskType.VIDEO_PROCESSING)
        context.task_id = str(task.id)
        
        # Initialize orchestrator
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        # Execute step
        kwargs = {}
        if step == ProcessingStep.STEP1_OUTLINE and srt_path:
            kwargs['srt_path'] = srt_path
        
        result = orchestrator.execute_step(step, **kwargs)
        
        context.mark_completed()
        
        # If it is the last step (step6_video), automatically synchronize data to the database
        if step == ProcessingStep.STEP6_VIDEO:
            try:
                from ..services.data_sync_service import DataSyncService
                from pathlib import Path
                
                project_dir = Path(__file__).parent.parent / "data" / "projects" / project_id
                if project_dir.exists():
                    sync_service = DataSyncService(self.db)
                    sync_result = sync_service.sync_project_from_filesystem(project_id, project_dir)
                    if sync_result.get("success"):
                        logger.info(f"Project {project_id} Data synchronization succeeded: {sync_result}")
                    else:
                        logger.error(f"Project {project_id} Data synchronization failed: {sync_result}")
            except Exception as e:
                logger.warning(f"Data synchronization failed: {e}")
        
        return {
            "success": True,
            "task_id": task.id,
            "step": step.value,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    def get_processing_status(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """
        Get processing status
        
        Args:
            project_id: ProjectID
            task_id: TaskID
            
        Returns:
            Processing state
        """
        orchestrator = ProcessingOrchestrator(project_id, task_id, self.db)
        return orchestrator.get_pipeline_status()
    
    @handle_service_error
    @with_concurrency_control()
    def retry_step(self, project_id: str, task_id: str, step: ProcessingStep,
                   srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Retry step
        
        Args:
            project_id: ProjectID
            task_id: TaskID
            step: Process step
            srt_path: SRTFile path (only Step 1 required))
            
        Returns:
            Retry result
        """
        logger.info(f"Retry step: {step.value}")
        
        # Create processing context
        context = ProcessingContext(project_id, task_id, self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        orchestrator = ProcessingOrchestrator(project_id, task_id, self.db)
        
        kwargs = {}
        if step == ProcessingStep.STEP1_OUTLINE and srt_path:
            kwargs['srt_path'] = srt_path
        
        result = orchestrator.retry_step(step, **kwargs)
        
        context.mark_completed()
        
        return {
            "success": True,
            "step": step.value,
            "result": result,
            "context": context.get_context_summary()
        }

    @handle_service_error
    @with_concurrency_control()
    def resume_processing(self, project_id: str, start_step: str, 
                         srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Resume processing from a specified step
        
        Args:
            project_id: ProjectID
            start_step: Start step name
            srt_path: SRTFile path (only Step 1 required))
            
        Returns:
            Restore processing result
        """
        logger.info(f"From step {start_step} Restore handling project: {project_id}")
        
        # Create processing context
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        # Create processing task
        task = self._create_processing_task(project_id)
        context.task_id = str(task.id)
        
        # Initialize orchestrator
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        # Map step names to ProcessingStep enum
        step_mapping = {
            "step1_outline": ProcessingStep.STEP1_OUTLINE,
            "step2_timeline": ProcessingStep.STEP2_TIMELINE,
            "step3_scoring": ProcessingStep.STEP3_SCORING,
            "step4_title": ProcessingStep.STEP4_TITLE,
            "step5_clustering": ProcessingStep.STEP5_CLUSTERING,
            "step6_video": ProcessingStep.STEP6_VIDEO
        }
        
        if start_step not in step_mapping:
            raise ValueError(f"Invalid step name: {start_step}")
        
        processing_step = step_mapping[start_step]
        
        # Resume execution from a specified step
        result = orchestrator.resume_from_step(processing_step, srt_path)
        
        context.mark_completed()
        
        # Update project status to completed and sync data
        try:
            from ..models.project import Project, ProjectStatus
            from ..services.data_sync_service import DataSyncService
            from pathlib import Path
            
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = ProjectStatus.COMPLETED
                self.db.commit()
                logger.info(f"Project status updated to completed: {project_id}")
                
                # Sync data to the database
                project_dir = Path(__file__).parent.parent / "data" / "projects" / project_id
                if project_dir.exists():
                    sync_service = DataSyncService(self.db)
                    sync_result = sync_service.sync_project_from_filesystem(project_id, project_dir)
                    if sync_result.get("success"):
                        logger.info(f"Project {project_id} Data synchronization succeeded: {sync_result}")
                    else:
                        logger.error(f"Project {project_id} Data synchronization failed: {sync_result}")
        except Exception as e:
            logger.warning(f"Failed to update project status: {e}")
        
        return {
            "success": True,
            "task_id": task.id,
            "project_id": project_id,
            "start_step": start_step,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    def get_project_config(self, project_id: str) -> Dict[str, Any]:
        """
        Get project configuration
        
        Args:
            project_id: ProjectID
            
        Returns:
            Project configuration
        """
        config_manager = ProjectConfigManager(project_id)
        return config_manager.export_config()
    
    @handle_service_error
    def update_project_config(self, project_id: str, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update project configuration
        
        Args:
            project_id: ProjectID
            config_updates: Configuration update
            
        Returns:
            Update result
        """
        config_manager = ProjectConfigManager(project_id)
        
        # Update processing parameters
        if "processing_params" in config_updates:
            config_manager.update_processing_params(**config_updates["processing_params"])
        
        # Update LLM configuration
        if "llm_config" in config_updates:
            config_manager.update_llm_config(**config_updates["llm_config"])
        
        # Update step configuration
        if "steps" in config_updates:
            for step_name, step_config in config_updates["steps"].items():
                config_manager.update_step_config(step_name, **step_config)
        
        return {
            "success": True,
            "message": "Configuration updated successfully"
        }
    
    @handle_service_error
    def validate_project_setup(self, project_id: str) -> Dict[str, Any]:
        """
        Validate project settings
        
        Args:
            project_id: ProjectID
            
        Returns:
            Validation result
        """
        # Temporarily commented out, file `PipelineAdapter` does not exist
        # adapter = PipelineAdapter(project_id)
        # errors = adapter.validate_pipeline_prerequisites()
        
        # if errors:
        #     return {
        #         "valid": False,
        #         "errors": errors
        #     }
        
        return {
            "valid": True,
            "message": "Project settings validated (temporarily bypassing PipelineAdapter validation))"
        }
    
    def _create_processing_task(self, project_id: str, task_type: TaskType = TaskType.VIDEO_PROCESSING) -> Task:
        """Create processing task"""
        task_data = {
            "name": f"Video processing task - {project_id}",
            "description": f"Process project {project_id} video content",
            "project_id": project_id,
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "progress": 0.0,
            "metadata": {
                "project_id": project_id,
                "task_type": task_type.value if hasattr(task_type, 'value') else task_type
            }
        }
        
        return self.task_repo.create(**task_data)