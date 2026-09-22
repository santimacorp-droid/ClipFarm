#!/usr/bin/env python3
"""
Thumbnail generation script for existing projects
"""

import sys
from pathlib import Path

# Add project root directory toPythonPath
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.core.database import SessionLocal
from backend.models.project import Project
from backend.utils.thumbnail_generator import generate_project_thumbnail
from sqlalchemy import text

def generate_thumbnails_for_projects():
    """Generate thumbnails for all projects missing thumbnails"""
    db = SessionLocal()
    try:
        # Find projects without thumbnails but with video files
        projects = db.query(Project).filter(
            Project.thumbnail.is_(None),
            Project.video_path.isnot(None)
        ).all()
        
        if not projects:
            print("✅ All projects already have thumbnails")
            return True
        
        print(f"📋 Found {len(projects)} projects needing thumbnail generation")
        
        success_count = 0
        for project in projects:
            try:
                print(f"🎬 Preparing project '{project.name}' ({project.id}) Generating thumbnail...")
                
                # Check if video file exists
                video_path = Path(project.video_path)
                if not video_path.exists():
                    print(f"⚠️  Video file does not exist: {video_path}")
                    continue
                
                # Generating thumbnail
                thumbnail_data = generate_project_thumbnail(project.id, video_path)
                
                if thumbnail_data:
                    # Saved to database
                    project.thumbnail = thumbnail_data
                    db.commit()
                    print(f"✅ Project '{project.name}' Thumbnail generation succeeded")
                    success_count += 1
                else:
                    print(f"❌ Project '{project.name}' Thumbnail generation failed")
                    
            except Exception as e:
                print(f"❌ Project '{project.name}' Processing failed: {e}")
                db.rollback()
                continue
        
        print(f"🎉 Done! Successfully generated thumbnails for {success_count}/{len(projects)} projects generated thumbnails")
        return True
        
    except Exception as e:
        print(f"❌ Error occurred during thumbnail generation process: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def generate_thumbnail_for_project(project_id: str):
    """Generate thumbnail for specified project"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            print(f"❌ Project {project_id} Not found")
            return False
        
        if not project.video_path:
            print(f"❌ Project {project_id} No video files")
            return False
        
        # Check if video file exists
        video_path = Path(project.video_path)
        if not video_path.exists():
            print(f"❌ Video file does not exist: {video_path}")
            return False
        
        print(f"🎬 Preparing project '{project.name}' ({project.id}) Generating thumbnail...")
        
        # Generating thumbnail
        thumbnail_data = generate_project_thumbnail(project.id, video_path)
        
        if thumbnail_data:
            # Saved to database
            project.thumbnail = thumbnail_data
            db.commit()
            print(f"✅ Project '{project.name}' Thumbnail generation succeeded")
            return True
        else:
            print(f"❌ Project '{project.name}' Thumbnail generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Processing project {project_id} while processing: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def main():
    """Main function"""
    if len(sys.argv) > 1:
        # Generate thumbnail for specified project
        project_id = sys.argv[1]
        print(f"🚀 Starting project {project_id} Generating thumbnail...")
        if generate_thumbnail_for_project(project_id):
            print("🎉 Thumbnail generation complete!! ")
        else:
            print("❌ Thumbnail generation failed")
            sys.exit(1)
    else:
        # Generate thumbnails for all projects
        print("🚀 Starting thumbnail generation for all projects...")
        if generate_thumbnails_for_projects():
            print("🎉 Thumbnail generation complete! ")
        else:
            print("❌ Thumbnail generation failed")
            sys.exit(1)

if __name__ == "__main__":
    main()
