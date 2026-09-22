"""
ProjectRepository
Provides data access operations related to projects
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from pathlib import Path
from .base import BaseRepository
from ..models.project import Project, ProjectStatus, ProjectType

class ProjectRepository(BaseRepository[Project]):
    """Project Repository class"""
    
    def __init__(self, db: Session):
        super().__init__(Project, db)
    
    def get_by_status(self, status: ProjectStatus) -> List[Project]:
        """
        Retrieves a list of projects by status
        
        Args:
            status: Project status
            
        Returns:
            Project list
        """
        return self.find_by(status=status)
    
    def get_by_category(self, category: ProjectType) -> List[Project]:
        """
        Retrieves a list of projects based on type
        
        Args:
            category: Project type
            
        Returns:
            Project list
        """
        return self.find_by(project_type=category)
    
    def get_recent_projects(self, limit: int = 10) -> List[Project]:
        """
        Gets the most recently created projects
        
        Args:
            limit: Return number limit
            
        Returns:
            Recent list of projects
        """
        return self.db.query(self.model).order_by(
            desc(self.model.created_at)
        ).limit(limit).all()
    
    def create_project(self, project_data: Dict[str, Any]) -> Project:
        """Creates a project record (separation storage mode))"""
        from ..services.storage_service import StorageService
        import uuid
        
        # Generates a project ID (if one is not provided)
        if "id" not in project_data:
            project_data["id"] = str(uuid.uuid4())
        
        # Initialize storage service
        storage_service = StorageService(project_data["id"])
        
        # Create project record
        project = Project(
            id=project_data["id"],
            name=project_data["name"],
            description=project_data.get("description"),
            project_type=project_data.get("project_type", ProjectType.DEFAULT),
            status=project_data.get("status", ProjectStatus.PENDING),
            processing_config=project_data.get("processing_config", {}),
            project_metadata={
                'project_id': project_data["id"],
                'created_at': project_data.get("created_at"),
                'storage_service_initialized': True
            }
        )
        
        self.db.add(project)
        self.db.commit()
        return project
    
    def get_project_file_paths(self, project_id: str) -> Dict[str, Optional[Path]]:
        """Retrieves the project file path"""
        project = self.get_by_id(project_id)
        if not project:
            return {}
        
        return {
            "video_path": Path(project.video_path) if project.video_path else None,
            "subtitle_path": Path(project.subtitle_path) if project.subtitle_path else None
        }
    
    def update_project_file_path(self, project_id: str, file_type: str, file_path: str) -> bool:
        """Updates the project file path"""
        project = self.get_by_id(project_id)
        if not project:
            return False
        
        if file_type == "video":
            project.video_path = file_path
        elif file_type == "subtitle":
            project.subtitle_path = file_path
        else:
            return False
        
        self.db.commit()
        return True
    
    def get_project_storage_info(self, project_id: str) -> Dict[str, Any]:
        """Retrieves project storage information"""
        from ..services.storage_service import StorageService
        
        project = self.get_by_id(project_id)
        if not project:
            return {}
        
        storage_service = StorageService(project_id)
        storage_info = storage_service.get_project_storage_info()
        
        return {
            "project_id": project_id,
            "storage_info": storage_info,
            "file_paths": {
                "video_path": project.video_path,
                "subtitle_path": project.subtitle_path
            }
        }
    
    def get_processing_projects(self) -> List[Project]:
        """
        Gets the project currently being processed
        
        Returns:
            List of projects currently being processed
        """
        return self.find_by(status=ProjectStatus.PROCESSING)
    
    def get_completed_projects(self) -> List[Project]:
        """
        Retrieves completed projects
        
        Returns:
            List of completed projects
        """
        return self.find_by(status=ProjectStatus.COMPLETED)
    
    def get_error_projects(self) -> List[Project]:
        """
        Retrieves projects with errors
        
        Returns:
            List of projects with errors
        """
        return self.find_by(status=ProjectStatus.FAILED)
    
    def search_projects(self, keyword: str) -> List[Project]:
        """
        Search projects
        
        Args:
            keyword: Search keyword
            
        Returns:
            List of matching projects
        """
        return self.db.query(self.model).filter(
            self.model.name.contains(keyword) | 
            self.model.description.contains(keyword)
        ).all()
    
    def get_projects_with_clips_count(self, skip: int = 0, limit: int = 100) -> List[Project]:
        """
        Retrieves a list of projects including slice counts
        
        Args:
            skip: Skipped record count
            limit: Limit on number of records returned
            
        Returns:
            Project list
        """
        return self.db.query(self.model).options(
            # Here you can add preloading options to reduce N+1 query issues
        ).offset(skip).limit(limit).all()
    
    def get_project_with_details(self, project_id: str) -> Optional[Project]:
        """
        Retrieves project details including associated slices and collections
        
        Args:
            project_id: ProjectID
            
        Returns:
            Project instance orNone
        """
        return self.db.query(self.model).filter(
            self.model.id == project_id
        ).first()
    
    def update_project_status(self, project_id: str, status: ProjectStatus) -> Optional[Project]:
        """
        Update project status
        
        Args:
            project_id: ProjectID
            status: New status
            
        Returns:
            Updated project instance orNone
        """
        return self.update(project_id, status=status)
    
    def get_projects_by_date_range(self, start_date, end_date) -> List[Project]:
        """
        Retrieves projects by date range
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Project list
        """
        return self.db.query(self.model).filter(
            self.model.created_at >= start_date,
            self.model.created_at <= end_date
        ).order_by(desc(self.model.created_at)).all()
    
    def get_project_statistics(self) -> dict:
        """
        Retrieves project statistics
        
        Returns:
            Statistics information dictionary
        """
        total_projects = self.count()
        processing_projects = len(self.get_processing_projects())
        completed_projects = len(self.get_completed_projects())
        error_projects = len(self.get_error_projects())
        
        return {
            "total": total_projects,
            "processing": processing_projects,
            "completed": completed_projects,
            "error": error_projects,
            "success_rate": (completed_projects / total_projects * 100) if total_projects > 0 else 0
        }