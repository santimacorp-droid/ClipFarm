#!/usr/bin/env python3
"""
Fix project thumbnail script
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
import requests
import base64
import logging

logger = logging.getLogger(__name__)

def fix_project_thumbnail(project_id: str):
    """Fixing thumbnails for specified projects"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            print(f"❌ Project {project_id} Does not exist")
            return False
        
        if project.thumbnail:
            print(f"✅ Project {project_id} Existing thumbnail, skip")
            return True
        
        print(f"🔧 Repair project {project_id} Thumbnail for...")
        
        # Check project type and source
        source_url = project.project_metadata.get('source_url') if project.project_metadata else None
        is_bilibili_project = source_url and 'bilibili.com' in source_url
        has_video_file = project.video_path and Path(project.video_path).exists()
        
        if is_bilibili_project:
            # For link-imported project - attempt toBGet thumbnail for site
            print(f"📺 DetectedBFor site project, attempt to get original video thumbnail...")
            success = fix_bilibili_thumbnail(project, db)
        elif has_video_file:
            # File import project - generating thumbnail from video file
            print(f"📁 Detected file-imported project, generating thumbnail from video file...")
            success = fix_file_import_thumbnail(project, db)
        else:
            # No original video file, attempting to generate thumbnail from slices
            print(f"🎬 No original video file, attempting to generate thumbnail from slices...")
            success = fix_clip_thumbnail(project, db)
        
        if success:
            print(f"✅ Project {project_id} Thumbnail repair succeeded")
        else:
            print(f"❌ Project {project_id} Thumbnail repair failed")
        
        return success
        
    except Exception as e:
        print(f"❌ Repair project {project_id} Error during thumbnail generation: {e}")
        return False
    finally:
        db.close()

def fix_bilibili_thumbnail(project, db):
    """RepairBSite thumbnails for projects"""
    try:
        # Get from project settingsBSite information
        if not project.processing_config:
            return False
        
        bilibili_info = project.processing_config.get('bilibili_info', {})
        if not bilibili_info:
            return False
        
        # Try fromBSiteAPIGet thumbnail
        # Here the actual image based on the video frame will be usedBSiteAPITo implement
        # Temporarily returnFalse, Mark needing manual handling
        print("⚠️  BNeed to get site thumbnailAPINot supported, temporarily skipped")
        return False
        
    except Exception as e:
        logger.error(f"RepairBSite thumbnail failed: {e}")
        return False

def fix_file_import_thumbnail(project, db):
    """Fixing thumbnails for file-imported projects"""
    try:
        video_path = Path(project.video_path)
        if not video_path.exists():
            print(f"⚠️  Video file not exists: {video_path}")
            return False
        
        # Generate thumbnail
        thumbnail_data = generate_project_thumbnail(project.id, video_path)
        
        if thumbnail_data:
            # Save to database
            project.thumbnail = thumbnail_data
            db.commit()
            return True
        else:
            print("⚠️  Thumbnail generation failed")
            return False
            
    except Exception as e:
        logger.error(f"Thumbnail fix for file import failed: {e}")
        return False

def fix_clip_thumbnail(project, db):
    """Generate thumbnail from slice"""
    try:
        # Find slice files in project directory
        from backend.core.path_utils import get_project_directory
        project_dir = get_project_directory(str(project.id))
        clips_dir = project_dir / "output" / "clips"
        
        if not clips_dir.exists():
            print(f"⚠️  Slice directory does not exist: {clips_dir}")
            return False
        
        # Get first slice file
        clip_files = list(clips_dir.glob("*.mp4"))
        if not clip_files:
            print(f"⚠️  Slice file not found")
            return False
        
        first_clip = clip_files[0]
        print(f"🎬 Using slice files to generate thumbnail: {first_clip.name}")
        
        # Generate thumbnail
        thumbnail_data = generate_project_thumbnail(project.id, first_clip)
        
        if thumbnail_data:
            # Save to database
            project.thumbnail = thumbnail_data
            db.commit()
            return True
        else:
            print("⚠️  Slice-based thumbnail generation failed")
            return False
            
    except Exception as e:
        logger.error(f"Slice-based thumbnail generation failed: {e}")
        return False

def fix_all_project_thumbnails():
    """Fixing all project thumbnails"""
    db = SessionLocal()
    try:
        # Finding all projects without thumbnails
        projects = db.query(Project).filter(Project.thumbnail.is_(None)).all()
        
        if not projects:
            print("✅ All projects already have thumbnails")
            return True
        
        print(f"📋 Find {len(projects)} projects needing thumbnail repair")
        
        success_count = 0
        for project in projects:
            if fix_project_thumbnail(project.id):
                success_count += 1
        
        print(f"🎉 Done! Successfully fixed {success_count}/{len(projects)} Thumbnails for projects")
        return True
        
    except Exception as e:
        print(f"❌ Error occurred during fix of all project thumbnails: {e}")
        return False
    finally:
        db.close()

def main():
    """Main function"""
    if len(sys.argv) > 1:
        # Repair specified project
        project_id = sys.argv[1]
        print(f"🚀 Starting repair of project {project_id} Thumbnail for...")
        if fix_project_thumbnail(project_id):
            print("🎉 Thumbnail repair done! ")
        else:
            print("❌ Thumbnail repair failed")
            sys.exit(1)
    else:
        # Repair all projects
        print("🚀 Starting to fix thumbnails for all projects...")
        if fix_all_project_thumbnails():
            print("🎉 All thumbnail repairs complete! ")
        else:
            print("❌ Thumbnail repair failed")
            sys.exit(1)

if __name__ == "__main__":
    main()
