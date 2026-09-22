#!/usr/bin/env python3
"""
Generate collection cover thumbnails for all
"""
import sys
import os
from pathlib import Path

# Add project root directory toPythonPath
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.core.database import get_db
from backend.models.collection import Collection
from backend.utils.video_processor import VideoProcessor
import logging

# Configuring logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_collection_thumbnails():
    """Generate thumbnails for all collections without covers"""
    try:
        db = next(get_db())
        
        # Find all collections without covers
        collections_without_thumbnails = db.query(Collection).filter(
            Collection.thumbnail_path.is_(None)
        ).all()
        
        if not collections_without_thumbnails:
            logger.info("All collections already have covers")
            return True
        
        logger.info(f"Found {len(collections_without_thumbnails)} collections without covers")
        
        success_count = 0
        for collection in collections_without_thumbnails:
            try:
                logger.info(f"Creating cover for collection '{collection.name}' ({collection.id}) Generating cover...")
                
                # Check for export video file
                if not collection.export_path:
                    logger.warning(f"Collection '{collection.name}' No export video file, skipping")
                    continue
                
                video_path = Path(collection.export_path)
                if not video_path.exists():
                    logger.warning(f"Collection '{collection.name}' does not exist: {video_path}")
                    continue
                
                # Generate cover filename
                safe_name = "".join(c for c in collection.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_name = safe_name.replace(' ', '_')
                thumbnail_filename = f"{collection.id}_{safe_name}_thumbnail.jpg"
                thumbnail_path = video_path.parent / thumbnail_filename
                
                # UsingVideoProcessorGenerating cover
                thumbnail_success = VideoProcessor.extract_thumbnail(video_path, thumbnail_path, time_offset=5)
                
                if thumbnail_success:
                    # Updating database
                    collection.thumbnail_path = str(thumbnail_path)
                    db.commit()
                    logger.info(f"✅ Collection '{collection.name}' Cover generated successfully: {thumbnail_path}")
                    success_count += 1
                else:
                    logger.error(f"❌ Collection '{collection.name}' Cover generation failed")
                    
            except Exception as e:
                logger.error(f"❌ Collection '{collection.name}' Processing failed: {e}")
                db.rollback()
                continue
        
        logger.info(f"🎉 Done! Successfully set for {success_count}/{len(collections_without_thumbnails)} collections generate cover")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error occurred during collection cover generation: {e}")
        return False
    finally:
        db.close()

def generate_thumbnail_for_collection(collection_id: str):
    """Generate thumbnail for specified collection"""
    try:
        db = next(get_db())
        
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            logger.error(f"Collection not found: {collection_id}")
            return False
        
        if collection.thumbnail_path:
            logger.info(f"Collection '{collection.name}' There is already a cover")
            return True
        
        # Check for export video file
        if not collection.export_path:
            logger.error(f"Collection '{collection.name}' No export video file found")
            return False
        
        video_path = Path(collection.export_path)
        if not video_path.exists():
            logger.error(f"Collection '{collection.name}' does not exist: {video_path}")
            return False
        
        # Generate cover filename
        safe_name = "".join(c for c in collection.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        thumbnail_filename = f"{collection.id}_{safe_name}_thumbnail.jpg"
        thumbnail_path = video_path.parent / thumbnail_filename
        
        # UsingVideoProcessorGenerating cover
        thumbnail_success = VideoProcessor.extract_thumbnail(video_path, thumbnail_path, time_offset=5)
        
        if thumbnail_success:
            # Updating database
            collection.thumbnail_path = str(thumbnail_path)
            db.commit()
            logger.info(f"✅ Collection '{collection.name}' Cover generated successfully: {thumbnail_path}")
            return True
        else:
            logger.error(f"❌ Collection '{collection.name}' Cover generation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error occurred when generating collection cover: {e}")
        return False
    finally:
        db.close()

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate collection cover thumbnail')
    parser.add_argument('--collection-id', help='Generate cover for specified collection')
    parser.add_argument('--all', action='store_true', help='Generate covers for all collections without covers')
    
    args = parser.parse_args()
    
    if args.collection_id:
        success = generate_thumbnail_for_collection(args.collection_id)
    elif args.all:
        success = generate_collection_thumbnails()
    else:
        print("Please specify --collection-id Or --all Parameters")
        return
    
    if success:
        print("Operation completed")
    else:
        print("Operation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
