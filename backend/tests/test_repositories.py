"""
RepositoryPattern test
"""

import sys, os
# Add project root directory tosys.path, Ensure can findbackendPackage
current_file = os.path.abspath(__file__)
backend_dir = os.path.dirname(os.path.dirname(current_file))  # backendDirectory / Catalog
project_root = os.path.dirname(backend_dir)  # autoclipRoot directory

# Add project root directory tosys.path, Like thisPythonCan findbackendPackage
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from backend.models.base import Base
import backend.core.database as db_module
from backend.core.database import get_db
from backend.repositories.factory import (
    get_project_repository,
    get_clip_repository,
    get_collection_repository,
    get_task_repository
)
from backend.models.project import ProjectStatus, ProjectType
from backend.models.clip import ClipStatus
from backend.models.collection import CollectionStatus
from backend.models.task import TaskStatus, TaskType

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

class TestRepositoryPattern:
    """RepositoryPattern test class"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self, monkeypatch):
        """Set isolated in-memory test database so real database is never wiped"""
        Base.metadata.create_all(bind=test_engine)
        def _get_test_db():
            session = TestSessionLocal()
            try:
                yield session
            finally:
                session.close()
        monkeypatch.setattr(db_module, "get_db", _get_test_db)
        monkeypatch.setattr(db_module, "SessionLocal", TestSessionLocal)
        yield
        Base.metadata.drop_all(bind=test_engine)
    
    def test_project_repository_crud(self):
        """Test projectRepository's / of / forCRUDOperation"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        
        # Create project
        project_data = {
            "name": "Test project",
            "description": "This is a test project",
            "project_type": ProjectType.KNOWLEDGE,
            "status": ProjectStatus.PENDING
        }
        
        project = project_repo.create(**project_data)
        assert project.id is not None
        assert project.name == "Test project"
        assert project.status == ProjectStatus.PENDING
        
        # Query project
        retrieved_project = project_repo.get_by_id(project.id)
        assert retrieved_project is not None
        assert retrieved_project.name == "Test project"
        
        # Update project
        updated_project = project_repo.update(project.id, status=ProjectStatus.PROCESSING)
        assert updated_project.status == ProjectStatus.PROCESSING
        
        # Delete project
        success = project_repo.delete(project.id)
        assert success is True
        
        # Verify delete
        deleted_project = project_repo.get_by_id(project.id)
        assert deleted_project is None
    
    def test_clip_repository_operations(self):
        """Test sliceRepositoryOf operation"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        clip_repo = get_clip_repository(db)
        
        # Create project
        project = project_repo.create(
            name="Test project",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # Create slice
        clip_data = {
            "project_id": project.id,
            "title": "Test slice",
            "description": "This is a test slice",
            "start_time": 0,
            "end_time": 60,
            "duration": 60,
            "score": 0.8,
            "status": ClipStatus.COMPLETED
        }
        
        clip = clip_repo.create(**clip_data)
        assert clip.project_id == project.id
        assert clip.title == "Test slice"
        
        # Test by project query slice
        project_clips = clip_repo.get_by_project(project.id)
        assert len(project_clips) == 1
        assert project_clips[0].id == clip.id
        
        # Test by state query slice
        completed_clips = clip_repo.get_by_status(ClipStatus.COMPLETED)
        assert len(completed_clips) == 1
        assert completed_clips[0].id == clip.id
        
        # Test high-score slice query
        high_score_clips = clip_repo.get_high_score_clips(project.id, min_score=0.7)
        assert len(high_score_clips) == 1
        assert high_score_clips[0].id == clip.id
    
    def test_collection_repository_operations(self):
        """Test suiteRepositoryOf operation"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        collection_repo = get_collection_repository(db)
        
        # Create project
        project = project_repo.create(
            name="Test project",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # Create set
        collection_data = {
            "project_id": project.id,
            "name": "Test suite",
            "description": "This is a test set",
            "theme": "Test topic",
            "clips_count": 5,
            "total_duration": 300,
            "status": CollectionStatus.COMPLETED
        }
        
        collection = collection_repo.create(**collection_data)
        assert collection.project_id == project.id
        assert collection.name == "Test suite"
        
        # Test by project query set
        project_collections = collection_repo.get_by_project(project.id)
        assert len(project_collections) == 1
        assert project_collections[0].id == collection.id
        
        # Test by topic query set
        theme_collections = collection_repo.get_by_theme(project.id, "Test topic")
        assert len(theme_collections) == 1
        assert theme_collections[0].id == collection.id
    
    def test_task_repository_operations(self):
        """Test taskRepositoryOf operation"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        task_repo = get_task_repository(db)
        
        # Create project
        project = project_repo.create(
            name="Test project",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # Create task
        task_data = {
            "project_id": project.id,
            "name": "Test task",
            "description": "This is a test task",
            "task_type": TaskType.VIDEO_PROCESSING,
            "status": TaskStatus.PENDING,
            "priority": 1
        }
        
        task = task_repo.create(**task_data)
        assert task.project_id == project.id
        assert task.name == "Test task"
        assert task.status == TaskStatus.PENDING
        
        # Test task status update
        task_repo.update_task_status(task.id, TaskStatus.RUNNING)
        updated_task = task_repo.get_by_id(task.id)
        assert updated_task.status == TaskStatus.RUNNING
        
        # Test task complete
        task_repo.update_task_status(task.id, TaskStatus.COMPLETED)
        completed_task = task_repo.get_by_id(task.id)
        assert completed_task.status == TaskStatus.COMPLETED
        
        # Test by project query task
        project_tasks = task_repo.get_by_project(project.id)
        assert len(project_tasks) == 1
        assert project_tasks[0].id == task.id
    
    def test_repository_statistics(self):
        """Test / Stress / TrialRepositoryStatistics function"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        clip_repo = get_clip_repository(db)
        collection_repo = get_collection_repository(db)
        task_repo = get_task_repository(db)
        
        # Create project
        project = project_repo.create(
            name="Test project statistics",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.COMPLETED
        )
        
        # Create multiple slices
        for i in range(5):
            clip_repo.create(
                project_id=project.id,
                title=f"Slice{i+1}",
                start_time=i*60,
                end_time=(i+1)*60,
                duration=60,
                score=0.7 + i*0.1,
                status=ClipStatus.COMPLETED
            )
        
        # Create multiple sets
        for i in range(3):
            collection_repo.create(
                project_id=project.id,
                name=f"Suite{i+1}",
                theme=f"Theme / Subject{i+1}",
                clips_count=2,
                total_duration=120,
                status=CollectionStatus.COMPLETED
            )
        
        # Create multiple tasks
        for i in range(6):
            task_repo.create(
                project_id=project.id,
                name=f"Task{i+1}",
                            task_type=TaskType.VIDEO_PROCESSING,
            status=TaskStatus.COMPLETED if i < 5 else TaskStatus.FAILED
            )
        
        # Test project statistics
        project_stats = project_repo.get_project_statistics()
        assert project_stats["total"] >= 1
        assert project_stats["completed"] >= 1
        
        # Test slice statistics
        clip_stats = clip_repo.get_clips_statistics(project.id)
        assert clip_stats["total"] == 5
        assert clip_stats["completed"] == 5
        assert clip_stats["avg_score"] > 0.7
        
        # Test set statistics
        collection_stats = collection_repo.get_collections_statistics(project.id)
        assert collection_stats["total"] == 3
        assert collection_stats["completed"] == 3
        
        # Test task statistics
        task_stats = task_repo.get_tasks_statistics(project.id)
        assert task_stats["total"] == 6
        assert task_stats["completed"] == 5
        assert task_stats["failed"] == 1
    
    def test_repository_search(self):
        """Test / Stress / TrialRepositorySearch function"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        clip_repo = get_clip_repository(db)
        
        # Create project
        project = project_repo.create(
            name="Search test projects",
            description="This is a project for searching tests",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # Create slice
        clip_repo.create(
            project_id=project.id,
            title="Slice containing keyword",
            description="This slice contains important keywords",
            start_time=0,
            end_time=60,
            duration=60,
            status=ClipStatus.COMPLETED
        )
        
        # Test project search
        search_results = project_repo.search_projects("Search test")
        assert len(search_results) == 1
        assert search_results[0].id == project.id
        
        # Test slice search
        clip_results = clip_repo.search_clips(project.id, "keyword")
        assert len(clip_results) == 1
        assert "keyword" in clip_results[0].title.lower() or "keyword" in clip_results[0].description.lower()

if __name__ == "__main__":
    # Run test
    pytest.main([__file__, "-v"]) 
