#!/usr/bin/env python3
"""
Database initialization script
"""

import sys
from pathlib import Path

# AddbackendPath toPythonPath
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from ..core.database import init_database, get_database_url
from ..core.config import init_paths, get_data_directory
from ..models.base import Base
from ..models.project import Project, ProjectStatus, ProjectType
from ..models.clip import Clip
from ..models.collection import Collection
from ..models.task import Task, TaskStatus, TaskType
from sqlalchemy.orm import Session
from ..core.database import SessionLocal

def create_initial_data():
    """Create initial test data"""
    db = SessionLocal()
    try:
        # Check for existing data
        existing_projects = db.query(Project).count()
        if existing_projects > 0:
            print("Database already has data, skipping initial data creation")
            return
        
        # Create test project
        test_project = Project(
            name="Test suite",
            description="This is a test project for system validation",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING,
            processing_config={
                "chunk_size": 5000,
                "min_score_threshold": 0.7,
                "max_clips_per_collection": 5
            }
        )
        db.add(test_project)
        db.commit()
        db.refresh(test_project)
        
        # Create test task
        test_task = Task(
            name="Test run",
            description="Test processing task",
            task_type=TaskType.VIDEO_PROCESSING,
            project_id=test_project.id,
            status=TaskStatus.PENDING,
            progress=0,
            current_step="Waiting to start",
            total_steps=6
        )
        db.add(test_task)
        
        # Create test slice
        test_clip = Clip(
            title="Test slice",
            content="This is the content of a test slice",
            start_time=0,
            end_time=30,
            score=0.8,
            project_id=test_project.id
        )
        db.add(test_clip)
        
        # Create test suite
        test_collection = Collection(
            title="Testsuite collection",
            description="This is a test suite",
            project_id=test_project.id
        )
        db.add(test_collection)
        
        db.commit()
        print("✅ Initial test data creation successful")
        
    except Exception as e:
        print(f"❌ Creating initial data failed: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main function"""
    print("🚀 Starting database initialization...")
    
    # Initialize path configuration
    init_paths()
    
    # Show database configuration
    print(f"DatabaseURL: {get_database_url()}")
    print(f"Data directory: {get_data_directory()}")
    
    # Initialize database
    if init_database():
        print("✅ Database initialization successful")
        
        # Create initial data
        create_initial_data()
        
        print("🎉 Database initialization complete! ")
    else:
        print("❌ Database initialization failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 