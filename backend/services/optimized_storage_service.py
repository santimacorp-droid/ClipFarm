"""
Optimize storage service - resolve double storage problem
Database stores only metadata, filesystem stores actual files
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..core.config import get_data_directory
from ..models.project import Project
from ..models.clip import Clip
from ..models.collection import Collection

logger = logging.getLogger(__name__)


class OptimizedStorageService:
    """Optimize storage service - store metadata in database, actual files in filesystem"""
    
    def __init__(self, db: Session, project_id: str):
        self.db = db
        self.project_id = project_id
        self.data_dir = get_data_directory()
        self.project_dir = self.data_dir / "projects" / project_id
        
        # Ensure project directory structure exists
        self._ensure_project_structure()
    
    def _ensure_project_structure(self):
        """Ensure project directory structure exists"""
        directories = [
            self.project_dir / "raw",           # source file
            self.project_dir / "processing",    # processing intermediate file
            self.project_dir / "output" / "clips",      # slice file
            self.project_dir / "output" / "collections" # collection file
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    # ==================== Manage project files ====================
    
    def save_project_file(self, file_path: Path, file_type: str = "video") -> str:
        """Save project file to filesystem, return relative path"""
        try:
            if file_type == "video":
                target_dir = self.project_dir / "raw"
                target_name = f"input_video{file_path.suffix}"
            elif file_type == "subtitle":
                target_dir = self.project_dir / "raw"
                target_name = f"input_subtitle{file_path.suffix}"
            else:
                target_dir = self.project_dir / "raw"
                target_name = file_path.name
            
            target_path = target_dir / target_name
            shutil.copy2(file_path, target_path)
            
            # Return relative path, for storage in database
            relative_path = f"projects/{self.project_id}/raw/{target_name}"
            logger.info(f"Project file saved: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to save project file: {e}")
            raise
    
    def get_project_file_path(self, relative_path: str) -> Path:
        """Get full file path from relative path"""
        return self.data_dir / relative_path
    
    # ==================== Manage slice files ====================
    
    def save_clip_file(self, clip_data: Dict[str, Any], clip_id: str) -> str:
        """Save slice file to filesystem, return relative path"""
        try:
            # This should contain actual slice file save logic
            # Temporarily return mock path
            clip_file = f"clip_{clip_id}.mp4"
            target_path = self.project_dir / "output" / "clips" / clip_file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create simulated file (actually save real slice file)
            target_path.touch()
            
            # returning relative path
            relative_path = f"projects/{self.project_id}/output/clips/{clip_file}"
            logger.info(f"slice fileSaved: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Savedslice fileFailed: {e}")
            raise
    
    def save_clip_metadata(self, clip_data: Dict[str, Any], clip_id: str) -> Clip:
        """Save slice metadata to database"""
        try:
            # Create slice record, store only metadata
            clip = Clip(
                id=clip_id,
                project_id=self.project_id,
                title=clip_data.get('title', ''),
                description=clip_data.get('description', ''),
                start_time=clip_data.get('start_time', 0),
                end_time=clip_data.get('end_time', 0),
                duration=clip_data.get('duration', 0),
                score=clip_data.get('score', 0.0),
                recommendation_reason=clip_data.get('recommendation_reason', ''),
                video_path=self.save_clip_file(clip_data, clip_id),  # Store relative path
                thumbnail_path=clip_data.get('thumbnail_path', ''),
                processing_step=clip_data.get('processing_step', 6),
                tags=clip_data.get('tags', []),
                clip_metadata=clip_data.get('metadata', {})  # Store trimmed metadata
            )
            
            self.db.add(clip)
            self.db.commit()
            self.db.refresh(clip)
            
            logger.info(f"Slice metadata saved to database: {clip_id}")
            return clip
            
        except Exception as e:
            logger.error(f"Failed to save slice metadata: {e}")
            self.db.rollback()
            raise
    
    # ==================== Manage bundle files ====================
    
    def save_collection_file(self, collection_data: Dict[str, Any], collection_id: str) -> str:
        """Save bundle file to filesystem, return relative path"""
        try:
            # This should contain actual bundle file save logic
            # Temporarily return mock path
            collection_file = f"collection_{collection_id}.mp4"
            target_path = self.project_dir / "output" / "collections" / collection_file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create simulated file (actually save real bundle file)
            target_path.touch()
            
            # returning relative path
            relative_path = f"projects/{self.project_id}/output/collections/{collection_file}"
            logger.info(f"collection fileSaved: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Savedcollection fileFailed: {e}")
            raise
    
    def save_collection_metadata(self, collection_data: Dict[str, Any], collection_id: str) -> Collection:
        """Save collection metadata to database"""
        try:
            # Create collection record, store only metadata
            collection = Collection(
                id=collection_id,
                project_id=self.project_id,
                name=collection_data.get('name', ''),
                description=collection_data.get('description', ''),
                clip_ids=collection_data.get('clip_ids', []),
                video_path=self.save_collection_file(collection_data, collection_id),  # Store relative path
                thumbnail_path=collection_data.get('thumbnail_path', ''),
                tags=collection_data.get('tags', []),
                collection_metadata=collection_data.get('metadata', {})  # Store trimmed metadata
            )
            
            self.db.add(collection)
            self.db.commit()
            self.db.refresh(collection)
            
            logger.info(f"Collection metadata saved to database: {collection_id}")
            return collection
            
        except Exception as e:
            logger.error(f"Failed to save collection metadata: {e}")
            self.db.rollback()
            raise
    
    # ==================== Manage intermediate files ====================
    
    def save_processing_metadata(self, metadata: Dict[str, Any], step: str) -> str:
        """Save processing intermediate metadata to filesystem"""
        try:
            metadata_file = self.project_dir / "processing" / f"{step}.json"
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Processing metadata saved: {metadata_file}")
            return str(metadata_file)
            
        except Exception as e:
            logger.error(f"Failed to save processing metadata: {e}")
            raise
    
    def get_processing_metadata(self, step: str) -> Optional[Dict[str, Any]]:
        """Get processing intermediate metadata"""
        try:
            metadata_file = self.project_dir / "processing" / f"{step}.json"
            
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get processing metadata: {e}")
            return None
    
    # ==================== Data query methods ====================
    
    def get_project_clips(self) -> List[Clip]:
        """Get all slices for project (from database)"""
        return self.db.query(Clip).filter(Clip.project_id == self.project_id).all()
    
    def get_project_collections(self) -> List[Collection]:
        """Get all bundles for project (from database)"""
        return self.db.query(Collection).filter(Collection.project_id == self.project_id).all()
    
    def get_clip_file_path(self, clip: Clip) -> Path:
        """Get full file path of slice"""
        if clip.video_path:
            return self.data_dir / clip.video_path
        return None
    
    def get_collection_file_path(self, collection: Collection) -> Path:
        """Get full file path of collection"""
        if collection.video_path:
            return self.data_dir / collection.video_path
        return None
    
    # ==================== Cleanup methods ====================
    
    def cleanup_temp_files(self):
        """Clean up temporary files"""
        temp_dir = self.data_dir / "temp"
        if temp_dir.exists():
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    temp_file.unlink()
                    logger.info(f"Clean up temporary files: {temp_file}")
    
    def cleanup_old_files(self, keep_days: int = 30):
        """cleaning up old files"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
            
            # Clean up old temporary files
            temp_dir = self.data_dir / "temp"
            if temp_dir.exists():
                for temp_file in temp_dir.iterdir():
                    if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_date.timestamp():
                        temp_file.unlink()
                        logger.info(f"Cleaning up old temporary files: {temp_file}")
            
            logger.info(f"Cleanup complete; kept {keep_days} files within days")
            
        except Exception as e:
            logger.error(f"cleaning up old filesFailed: {e}")
    
    # ==================== Data migration methods ====================
    
    def migrate_from_old_storage(self, old_project_dir: Path) -> Dict[str, Any]:
        """Migrate data from old storage format"""
        try:
            logger.info(f"Starting project data migration: {self.project_id}")
            
            migrated_files = []
            migrated_metadata = []
            
            # migrating source file
            if (old_project_dir / "raw").exists():
                for file_path in (old_project_dir / "raw").iterdir():
                    if file_path.is_file():
                        relative_path = self.save_project_file(file_path)
                        migrated_files.append(relative_path)
            
            # Migrate processing metadata
            if (old_project_dir / "processing").exists():
                for metadata_file in (old_project_dir / "processing").iterdir():
                    if metadata_file.suffix == '.json':
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        step_name = metadata_file.stem
                        self.save_processing_metadata(metadata, step_name)
                        migrated_metadata.append(step_name)
            
            # Migrate output files
            if (old_project_dir / "output").exists():
                # Migrate slice files
                clips_dir = old_project_dir / "output" / "clips"
                if clips_dir.exists():
                    for clip_file in clips_dir.iterdir():
                        if clip_file.is_file():
                            target_path = self.project_dir / "output" / "clips" / clip_file.name
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(clip_file, target_path)
                            migrated_files.append(f"projects/{self.project_id}/output/clips/{clip_file.name}")
                
                # Migrate collection files
                collections_dir = old_project_dir / "output" / "collections"
                if collections_dir.exists():
                    for collection_file in collections_dir.iterdir():
                        if collection_file.is_file():
                            target_path = self.project_dir / "output" / "collections" / collection_file.name
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(collection_file, target_path)
                            migrated_files.append(f"projects/{self.project_id}/output/collections/{collection_file.name}")
            
            logger.info(f"Data migration complete: {len(migrated_files)} files, {len(migrated_metadata)} metadata items")
            
            return {
                "success": True,
                "migrated_files": migrated_files,
                "migrated_metadata": migrated_metadata
            }
            
        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
