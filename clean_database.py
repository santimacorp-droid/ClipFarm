#!/usr/bin/env python3
"""
Cleared all project data from the database
"""
import sys
import os
from pathlib import Path

# Added project root directory toPythonPath
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.core.database import get_db
from backend.models.project import Project
from backend.models.clip import Clip
from backend.models.collection import Collection
from backend.models.task import Task
from sqlalchemy.orm import Session

def clean_database():
    """Cleared all project-related data from the database"""
    print("🧹 Starting database cleanup...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Deleted all data (by dependency order))
        print("Deleting task data...")
        deleted_tasks = db.query(Task).delete()
        print(f"✅ Deleted {deleted_tasks} tasks")
        
        print("Deleting collection data...")
        deleted_collections = db.query(Collection).delete()
        print(f"✅ Deleted {deleted_collections} collections")
        
        print("Deleting slice data...")
        deleted_clips = db.query(Clip).delete()
        print(f"✅ Deleted {deleted_clips} slices")
        
        print("Deleted project data...")
        deleted_projects = db.query(Project).delete()
        print(f"✅ Deleted {deleted_projects} projects")
        
        # Commit transaction
        db.commit()
        
        print("\n🎉 Database cleanup complete!")
        print("The database is now clean with no project data")
        
    except Exception as e:
        print(f"❌ An error occurred during database cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_database()
