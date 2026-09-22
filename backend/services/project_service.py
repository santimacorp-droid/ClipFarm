"""
Project service
Provides project-related business logic operations
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import shutil
import logging
from pathlib import Path

from ..services.base import BaseService
from ..repositories.project_repository import ProjectRepository
from ..models.project import Project
from ..models.task import Task
from ..models.clip import Clip
from ..models.collection import Collection
from ..schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter
from ..schemas.base import PaginationParams, PaginationResponse
from ..schemas.project import ProjectType, ProjectStatus
from ..schemas.task import TaskStatus

logger = logging.getLogger(__name__)


class ProjectService(BaseService[Project, ProjectCreate, ProjectUpdate, ProjectResponse]):
    """Project service with business logic."""
    
    def __init__(self, db: Session):
        repository = ProjectRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_project(self, project_data: ProjectCreate) -> Project:
        """Create a new project with business logic."""
        # Convert Pydantic schema to dict for repository
        project_dict = project_data.model_dump()
        
        # Map Pydantic fields to ORM fields
        orm_data = {
            "name": project_dict["name"],
            "description": project_dict.get("description"),
            "project_type": project_dict.get("project_type", "default").value if hasattr(project_dict.get("project_type", "default"), 'value') else project_dict.get("project_type", "default"),  # Map project_type to project_type
            "status": "pending",  # Default state is pending
            "video_path": project_dict.get("source_file"),  # Map source_file to video_path
            "processing_config": project_dict.get("settings", {}),  # Map settings to processing_config
            "project_metadata": {"source_url": project_dict.get("source_url")}  # Map source_url to metadata
        }
        
        return self.create(**orm_data)
    
    def update_project(self, project_id: str, project_data: ProjectUpdate) -> Optional[Project]:
        """Update a project with business logic."""
        # Filter out None values
        update_data = {k: v for k, v in project_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(project_id)
        
        # Map schema fields to ORM fields
        orm_data = {}
        for key, value in update_data.items():
            if key == "settings":
                orm_data["processing_config"] = value
            elif key == "processing_config":
                orm_data["processing_config"] = value
            else:
                orm_data[key] = value
        
        return self.update(project_id, **orm_data)
    
    def get_project_with_stats(self, project_id: str) -> Optional[ProjectResponse]:
        """Get project with statistics."""
        project = self.get(project_id)
        if not project:
            return None
        
        # Get actual statistics from database
        from ..models.clip import Clip
        from ..models.collection import Collection
        from ..models.task import Task
        
        total_clips = self.db.query(Clip).filter(Clip.project_id == project_id).count()
        total_collections = self.db.query(Collection).filter(Collection.project_id == project_id).count()
        total_tasks = self.db.query(Task).filter(Task.project_id == project_id).count()
        
        # Convert to response schema
        return ProjectResponse(
            id=str(getattr(project, 'id', '')),
            name=str(getattr(project, 'name', '')),
            description=str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
            project_type=ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and getattr(project, 'project_type', None) is not None else ProjectType.DEFAULT,
            status=getattr(project, 'status', ProjectStatus.PENDING),
            source_url=project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
            source_file=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
            video_path=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,  # Add video_path field for frontend use
            thumbnail=getattr(project, 'thumbnail', None),  # Retrieve thumbnail from database
            settings=getattr(project, 'processing_config', {}) or {},
            processing_config=getattr(project, 'processing_config', {}) or {},
            created_at=self._convert_utc_to_local(getattr(project, 'created_at', None)),
            updated_at=self._convert_utc_to_local(getattr(project, 'updated_at', None)),
            completed_at=self._convert_utc_to_local(getattr(project, 'completed_at', None)),
            total_clips=total_clips,
            total_collections=total_collections,
            total_tasks=total_tasks
        )
    
    def get_projects_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[ProjectFilter] = None
    ) -> ProjectListResponse:
        """Get paginated projects with filtering."""
        # Convert filters to dict
        filter_dict = {}
        if filters:
            filter_data = filters.model_dump()
            filter_dict = {k: v for k, v in filter_data.items() if v is not None}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        # Convert to response schemas
        project_responses = []
        for project in items:
            # Get actual statistics for each project
            from ..models.clip import Clip
            from ..models.collection import Collection
            from ..models.task import Task
            
            project_id = str(project.id)
            total_clips = self.db.query(Clip).filter(Clip.project_id == project_id).count()
            total_collections = self.db.query(Collection).filter(Collection.project_id == project_id).count()
            total_tasks = self.db.query(Task).filter(Task.project_id == project_id).count()
            
            project_responses.append(ProjectResponse(
                id=str(getattr(project, 'id', '')),
                name=str(getattr(project, 'name', '')),
                description=str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
                project_type=ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and hasattr(getattr(project, 'project_type'), 'value') else ProjectType.DEFAULT,
                status=ProjectStatus(getattr(project, 'status').value) if hasattr(project, 'status') and hasattr(getattr(project, 'status'), 'value') else ProjectStatus.PENDING,
                source_url=project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
                source_file=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
                video_path=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,  # Add video_path field for frontend use
                thumbnail=getattr(project, 'thumbnail', None),  # Retrieve thumbnail from database
                settings=getattr(project, 'processing_config', {}) or {},
                processing_config=getattr(project, 'processing_config', {}) or {},
                created_at=self._convert_utc_to_local(getattr(project, 'created_at', None)),
                updated_at=self._convert_utc_to_local(getattr(project, 'updated_at', None)),
                completed_at=self._convert_utc_to_local(getattr(project, 'completed_at', None)),
                total_clips=total_clips,
                total_collections=total_collections,
                total_tasks=total_tasks
            ))
        
        return ProjectListResponse(
            items=project_responses,
            pagination=pagination_response
        )
    
    def start_project_processing(self, project_id: str) -> bool:
        """Start processing a project."""
        project = self.get(project_id)
        if not project or project.status != "pending":
            return False
        
        # Update status to processing
        self.update(project_id, status="processing")
        return True
    
    def complete_project(self, project_id: str) -> bool:
        """Mark project as completed."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status and completion time
        from datetime import datetime
        self.update(project_id, status="completed", completed_at=datetime.utcnow())
        return True
    
    def fail_project(self, project_id: str, error_message: str = None) -> bool:
        """Mark project as failed."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status and add error message to settings
        settings = project.settings or {}
        if error_message:
            settings["error_message"] = error_message
        
        self.update(project_id, status="failed", settings=settings)
        return True
    
    def update_project_status(self, project_id: str, status: str) -> bool:
        """Update project status."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status
        self.update(project_id, status=status)
        return True
    
    def _convert_utc_to_local(self, dt):
        """Convert UTC time to local time (time zone information lost during SQLite storage))"""
        if dt is None:
            return None
        
        from datetime import datetime, timezone
        import pytz
        
        # Since SQLite loses timezone information during storage, we assume these times are UTC
        # Convert to local time
        local_tz = pytz.timezone('Asia/Shanghai')
        utc_time = dt.replace(tzinfo=timezone.utc)
        local_time = utc_time.astimezone(local_tz)
        
        return local_time
    
    def delete_project_with_files(self, project_id: str) -> bool:
        """
        Deletes a project and all its associated data
        
        Args:
            project_id: projectID
            
        Returns:
            Whether deletion was successful
        """
        try:
            # Get project information
            project = self.get(project_id)
            if not project:
                logger.warning(f"project {project_id} Does not exist")
                return False
            
            logger.info(f"Initiate deletion of project {project_id}: {project.name}")
            
            # Check if there are any running tasks (checking only non-completed projects)
            if project.status not in ["completed", "failed"]:
                running_tasks = self.db.query(Task).filter(
                    Task.project_id == project_id,
                    Task.status == TaskStatus.RUNNING
                ).count()
                
                if running_tasks > 0:
                    logger.warning(f"project {project_id} has {running_tasks} tasks are running and cannot be deleted")
                    return False
            else:
                # For completed or failed projects, log task status but do not block deletion
                running_tasks = self.db.query(Task).filter(
                    Task.project_id == project_id,
                    Task.status == TaskStatus.RUNNING
                ).count()
                
                if running_tasks > 0:
                    logger.info(f"project {project_id} Completed, but there is still {running_tasks} to be deleted along with it")
            
            # Begin transaction (if not already started)
            if not self.db.in_transaction():
                self.db.begin()
            
            try:
                # Delete related tasks
                task_count = self.db.query(Task).filter(Task.project_id == project_id).count()
                if task_count > 0:
                    self.db.query(Task).filter(Task.project_id == project_id).delete()
                    logger.info(f"Delete project {project_id} of {task_count} tasks")
                
                # Delete related slices
                clip_count = self.db.query(Clip).filter(Clip.project_id == project_id).count()
                if clip_count > 0:
                    self.db.query(Clip).filter(Clip.project_id == project_id).delete()
                    logger.info(f"Delete project {project_id} of {clip_count} slices")
                
                # Delete related collections
                collection_count = self.db.query(Collection).filter(Collection.project_id == project_id).count()
                if collection_count > 0:
                    self.db.query(Collection).filter(Collection.project_id == project_id).delete()
                    logger.info(f"Delete project {project_id} of {collection_count} collections")
                
                # Delete project record
                self.db.query(Project).filter(Project.id == project_id).delete()
                logger.info(f"Delete project {project_id} record(s)")
                
                # Commit transaction
                self.db.commit()
                
                # Remove project file
                self._delete_project_files(project_id)
                
                # Clean up progress data
                self._cleanup_project_progress(project_id)
                
                logger.info(f"project {project_id} Deletion successful")
                return True
                
            except Exception as e:
                self.db.rollback()
                logger.error(f"Delete project {project_id} Database operation failed: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"Delete project {project_id} occurring error: {str(e)}")
            return False
    
    def _delete_project_files(self, project_id: str):
        """
        Delete files associated with project
        
        Args:
            project_id: projectID
        """
        try:
            # Project directory path
            project_dir = Path(f"data/projects/{project_id}")
            
            if project_dir.exists():
                logger.info(f"Delete project directory: {project_dir}")
                shutil.rmtree(project_dir)
            else:
                logger.info(f"Project directory does not exist: {project_dir}")
            
            # Delete related files in the global output directory (if they exist)
            # NOTE: Currently using project-specific directory, but retain cleanup of global directory in case of leftover files
            from ..core.path_utils import get_data_directory
            data_dir = get_data_directory()
            global_clips_dir = data_dir / "output" / "clips"
            global_collections_dir = data_dir / "output" / "collections"
            
            # Delete global output directory's slice files belonging to this project
            if global_clips_dir.exists():
                for clip_file in global_clips_dir.glob(f"*_{project_id}*"):
                    try:
                        clip_file.unlink()
                        logger.info(f"Delete global slice file: {clip_file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete global slice file {clip_file}: {e}")
            
            # Delete global output directory's assembly files belonging to this project
            if global_collections_dir.exists():
                for collection_file in global_collections_dir.glob(f"*_{project_id}*"):
                    try:
                        collection_file.unlink()
                        logger.info(f"Delete global collection file: {collection_file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete global assembly file {collection_file}: {e}")
            
        except Exception as e:
            logger.error(f"An error occurred while deleting project files: {str(e)}")
            # Do not raise exceptions; let the database delete proceed
    
    def _cleanup_project_progress(self, project_id: str):
        """
        Cleans up project-related progress data
        
        Args:
            project_id: projectID
        """
        try:
            # Clean Redis progress data
            try:
                from ..services.simple_progress import clear_progress
                clear_progress(project_id)
                logger.info(f"Clear project {project_id} of Redis progress data")
            except Exception as e:
                logger.warning(f"Failed to clean Redis progress data: {e}")
            
            # Clears cache in enhancement progress service
            try:
                from ..services.enhanced_progress_service import progress_service
                if project_id in progress_service.progress_cache:
                    del progress_service.progress_cache[project_id]
                    logger.info(f"Clear project {project_id} in-memory progress cache")
            except Exception as e:
                logger.warning(f"Failed to clean memory progress cache: {e}")
            
        except Exception as e:
            logger.error(f"Failed to clean project progress data: {str(e)}")
    
 