"""
Unified Storage Management Service
Ensure all components use identical path logic and data storage strategies
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class UnifiedStorageManager:
    """Unified Storage Manager"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize unified storage manager
        
        Args:
            project_root: Project root directory; automatically detects if None
        """
        self.project_root = project_root or self._get_project_root()
        self.data_dir = self.project_root / "data"
        self.output_dir = self.data_dir / "output"
        
        # Ensure critical directory exists
        self._ensure_directories()
    
    def _get_project_root(self) -> Path:
        """Get project root directory"""
        current_path = Path(__file__).parent  # backend/core/
        
        # Ascend to find project root directory
        while current_path.parent != current_path:
            if (current_path.parent / "frontend").exists() and (current_path.parent / "backend").exists():
                return current_path.parent
            current_path = current_path.parent
        
        # Uses default path if not found
        return Path(__file__).parent.parent.parent
    
    def _ensure_directories(self):
        """Ensure critical directory exists"""
        directories = [
            self.data_dir,
            self.output_dir,
            self.output_dir / "clips",
            self.output_dir / "collections",
            self.output_dir / "metadata",
            self.data_dir / "projects",
            self.data_dir / "uploads",
            self.data_dir / "temp",
            self.data_dir / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    # Project-related paths
    def get_project_directory(self, project_id: str) -> Path:
        """Get project directory"""
        project_dir = self.data_dir / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    
    def get_project_raw_directory(self, project_id: str) -> Path:
        """Get project raw file directory"""
        raw_dir = self.get_project_directory(project_id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir
    
    def get_project_output_directory(self, project_id: str) -> Path:
        """Get project output directory"""
        output_dir = self.get_project_directory(project_id) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def get_project_clips_directory(self, project_id: str) -> Path:
        """Get project slice directory"""
        clips_dir = self.get_project_output_directory(project_id) / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        return clips_dir
    
    def get_project_collections_directory(self, project_id: str) -> Path:
        """Get project collection directory"""
        collections_dir = self.get_project_output_directory(project_id) / "collections"
        collections_dir.mkdir(parents=True, exist_ok=True)
        return collections_dir
    
    def get_project_metadata_directory(self, project_id: str) -> Path:
        """Get project metadata directory"""
        metadata_dir = self.get_project_directory(project_id) / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        return metadata_dir
    
    # Build file path
    def get_video_file_path(self, project_id: str, filename: str) -> Path:
        """Get project video file path"""
        return self.get_project_raw_directory(project_id) / filename
    
    def get_srt_file_path(self, project_id: str, filename: str) -> Path:
        """Get project SRT file path"""
        return self.get_project_raw_directory(project_id) / filename
    
    def get_clip_file_path(self, project_id: str, clip_id: str, title: str) -> Path:
        """Get slice file path"""
        # Clean filename, remove special characters
        safe_title = self._sanitize_filename(title)
        return self.get_project_clips_directory(project_id) / f"{clip_id}_{safe_title}.mp4"
    
    def get_collection_file_path(self, project_id: str, collection_id: str, title: str) -> Path:
        """Get collection file path"""
        # Clean filename, remove special characters
        safe_title = self._sanitize_filename(title)
        return self.get_project_collections_directory(project_id) / f"{collection_id}_{safe_title}.mp4"
    
    def get_metadata_file_path(self, project_id: str, filename: str) -> Path:
        """Get project metadata file path"""
        return self.get_project_metadata_directory(project_id) / filename
    
    # File operation
    def save_metadata(self, project_id: str, filename: str, data: Dict[str, Any]) -> Path:
        """Save metadata to file"""
        metadata_file = self.get_metadata_file_path(project_id, filename)
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Metadata saved: {metadata_file}")
        return metadata_file
    
    def load_metadata(self, project_id: str, filename: str) -> Optional[Dict[str, Any]]:
        """Load metadata file"""
        metadata_file = self.get_metadata_file_path(project_id, filename)
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load metadata {metadata_file}: {e}")
        
        return None
    
    def file_exists(self, file_path: Union[str, Path]) -> bool:
        """Check if file exists"""
        return Path(file_path).exists()
    
    def get_file_size(self, file_path: Union[str, Path]) -> int:
        """Get file size (bytes))"""
        try:
            return Path(file_path).stat().st_size
        except Exception:
            return 0
    
    def get_file_modified_time(self, file_path: Union[str, Path]) -> Optional[datetime]:
        """Get file modification time"""
        try:
            timestamp = Path(file_path).stat().st_mtime
            return datetime.fromtimestamp(timestamp)
        except Exception:
            return None
    
    # Path validation and repair
    def validate_file_path(self, file_path: Union[str, Path]) -> bool:
        """Validate file path for safety"""
        try:
            file_path = Path(file_path).resolve()
            # Check if path is within allowed directory
            allowed_dirs = [
                self.data_dir,
                self.output_dir,
                self.project_root
            ]
            
            return any(file_path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs)
        except Exception:
            return False
    
    def fix_file_path(self, file_path: Union[str, Path], project_id: str, file_type: str = "clip") -> Optional[Path]:
        """
        Fix file path to ensure file is in correct location
        
        Args:
            file_path: Raw file path
            project_id: ProjectID
            file_type: File type ("clip", "collection", "raw")
            
        Returns:
            Fixed file path; returns if file does not existNone
        """
        original_path = Path(file_path)
        
        # If file exists and path is safe, return directly
        if original_path.exists() and self.validate_file_path(original_path):
            return original_path
        
        # Attempt to find file in standard locations
        if file_type == "clip":
            # Extract clip ID and title from filename
            filename = original_path.name
            if '_' in filename:
                parts = filename.split('_', 1)
                if len(parts) == 2:
                    clip_id = parts[0]
                    title = parts[1].replace('.mp4', '')
                    standard_path = self.get_clip_file_path(project_id, clip_id, title)
                    if standard_path.exists():
                        return standard_path
        
        elif file_type == "collection":
            # Extract collection ID and title from filename
            filename = original_path.name
            if '_' in filename:
                parts = filename.split('_', 1)
                if len(parts) == 2:
                    collection_id = parts[0]
                    title = parts[1].replace('.mp4', '')
                    standard_path = self.get_collection_file_path(project_id, collection_id, title)
                    if standard_path.exists():
                        return standard_path
            else:
                # Attempt to use filename directly as title
                title = filename.replace('.mp4', '')
                # Requires collection ID; temporarily returns None
                return None
        
        elif file_type == "raw":
            # Original file typically located in raw directory
            filename = original_path.name
            standard_path = self.get_project_raw_directory(project_id) / filename
            if standard_path.exists():
                return standard_path
        
        return None
    
    # Tool method
    def _sanitize_filename(self, filename: str) -> str:
        """Clean filename, remove special characters"""
        # Remove or replace special characters
        safe_chars = []
        for char in filename:
            if char.isalnum() or char in (' ', '-', '_', ', ', '. ', '? ', '! ', ': ', '; '):
                safe_chars.append(char)
            else:
                safe_chars.append('_')
        
        # Remove extra spaces and underscores
        result = ''.join(safe_chars).strip()
        result = result.replace(' ', '_')
        
        # Remove consecutive underscores
        while '__' in result:
            result = result.replace('__', '_')
        
        return result
    
    def get_storage_info(self, project_id: str) -> Dict[str, Any]:
        """Get project storage information"""
        project_dir = self.get_project_directory(project_id)
        
        info = {
            "project_id": project_id,
            "project_directory": str(project_dir),
            "raw_files": [],
            "clips": [],
            "collections": [],
            "metadata_files": [],
            "total_size": 0
        }
        
        # Scan raw file
        raw_dir = self.get_project_raw_directory(project_id)
        for file_path in raw_dir.iterdir():
            if file_path.is_file():
                info["raw_files"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        # Scan slice file
        clips_dir = self.get_project_clips_directory(project_id)
        for file_path in clips_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.mp4':
                info["clips"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        # Scan collection file
        collections_dir = self.get_project_collections_directory(project_id)
        for file_path in collections_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.mp4':
                info["collections"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        # Scan metadata file
        metadata_dir = self.get_project_metadata_directory(project_id)
        for file_path in metadata_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.json':
                info["metadata_files"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        return info

# Global instance
_storage_manager = None

def get_storage_manager() -> UnifiedStorageManager:
    """Get global storage manager instance"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = UnifiedStorageManager()
    return _storage_manager

