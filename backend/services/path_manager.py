"""
Path manager
Specializes in managing path operations related to the project
"""

import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class PathManager:
    """Path manager responsible for unified management of project paths"""
    
    def __init__(self, project_id: str, base_dir: str = "data/projects"):
        self.project_id = project_id
        # Use absolute path
        project_root = Path(__file__).parent.parent.parent
        self.base_dir = project_root / base_dir
        self.project_dir = self.base_dir / project_id
        
        # Define project directory structure
        self.directory_structure = {
            "project_dir": self.project_dir,
            "metadata_dir": self.project_dir / "metadata",
            "raw_dir": self.project_dir / "raw",
            "outputs_dir": self.project_dir / "outputs",
            "logs_dir": self.project_dir / "logs",
            "backups_dir": self.project_dir / "backups",
            "temp_dir": self.project_dir / "temp"
        }
        
        # Ensure directory structure exists
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensures that all required directories exist"""
        for dir_name, dir_path in self.directory_structure.items():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensure directory exists: {dir_name} -> {dir_path}")
    
    def get_project_paths(self) -> Dict[str, Path]:
        """Get project-related paths"""
        return self.directory_structure.copy()
    
    def get_step_paths(self, step_name: str) -> Dict[str, Path]:
        """
        Obtains paths relevant to the step
        
        Args:
            step_name: Step name
            
        Returns:
            Step-related paths
        """
        metadata_dir = self.directory_structure["metadata_dir"]
        
        return {
            "input_path": metadata_dir / f"{step_name}_input.json",
            "output_path": metadata_dir / f"{step_name}_output.json",
            "intermediate_dir": metadata_dir / f"{step_name}_intermediate",
            "log_path": self.directory_structure["logs_dir"] / f"{step_name}.log"
        }
    
    def get_step_input_path(self, step_name: str) -> Path:
        """Obtains the path to the step's input file"""
        return self.get_step_paths(step_name)["input_path"]
    
    def get_step_output_path(self, step_name: str) -> Path:
        """Obtains the path to the step's output file"""
        return self.get_step_paths(step_name)["output_path"]
    
    def get_step_intermediate_dir(self, step_name: str) -> Path:
        """Obtains the directory for intermediate files of the step"""
        return self.get_step_paths(step_name)["intermediate_dir"]
    
    def get_step_log_path(self, step_name: str) -> Path:
        """Obtains the path to the step's log file"""
        return self.get_step_paths(step_name)["log_path"]
    
    def get_backup_path(self, filename: str) -> Path:
        """Get backup file path"""
        return self.directory_structure["backups_dir"] / filename
    
    def get_temp_path(self, filename: str) -> Path:
        """Get temporary file path"""
        return self.directory_structure["temp_dir"] / filename
    
    def get_config_path(self) -> Path:
        """Get configuration file path"""
        return self.project_dir / "config.yaml"
    
    def get_srt_path(self) -> Path:
        """Obtains the path to the SRT file"""
        # Attempt to retrieve the SRT filename from the project configuration
        try:
            from .config_manager import ProjectConfigManager
            config_manager = ProjectConfigManager(self.project_id)
            project_config = config_manager.get_project_config()
            
            if project_config and "processing_config" in project_config:
                srt_file = project_config["processing_config"].get("srt_file")
                if srt_file:
                    return self.directory_structure["raw_dir"] / srt_file
            
            # If not found in configuration, attempt to locate the SRT file in the raw directory
            raw_dir = self.directory_structure["raw_dir"]
            srt_files = list(raw_dir.glob("*.srt"))
            if srt_files:
                return srt_files[0]
            
            return raw_dir / "transcript.srt"
        except Exception as e:
            logger.warning(f"Failed to get SRT path: {e}")
            return self.directory_structure["raw_dir"] / "transcript.srt"
    
    def get_video_path(self) -> Path:
        """Get video file path"""
        # Attempt to retrieve the video filename from the project configuration
        try:
            from .config_manager import ProjectConfigManager
            config_manager = ProjectConfigManager(self.project_id)
            project_config = config_manager.get_project_config()
            
            if project_config and "processing_config" in project_config:
                video_file = project_config["processing_config"].get("video_file")
                if video_file:
                    return self.directory_structure["raw_dir"] / video_file
            
            # If not found in configuration, attempt to locate the video file in the raw directory
            raw_dir = self.directory_structure["raw_dir"]
            video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".flv"]
            for ext in video_extensions:
                video_files = list(raw_dir.glob(f"*{ext}"))
                if video_files:
                    return video_files[0]
            
            return None
        except Exception as e:
            logger.warning(f"Failed to get video path: {e}")
            return None
            
            if project_config and "srt_file" in project_config:
                srt_filename = project_config["srt_file"]
                return self.directory_structure["raw_dir"] / srt_filename
        except Exception as e:
            logger.warning(f"Unable to obtain SRT filename from project configuration: {e}")
        
        # Revert to default filename
        return self.directory_structure["raw_dir"] / "transcript.srt"
    
    def get_prompt_dir(self) -> Path:
        """Obtains the path to the prompt directory"""
        # Points to the prompt folder relative to the project root directory using absolute paths
        project_root = Path(__file__).parent.parent.parent
        return project_root / "prompt"
    
    def create_step_directories(self, step_name: str):
        """Creates necessary directories for a specific step"""
        step_paths = self.get_step_paths(step_name)
        
        # Create intermediate files directory
        step_paths["intermediate_dir"].mkdir(parents=True, exist_ok=True)
        
        # Ensure log directory exists
        step_paths["log_path"].parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"For step {step_name} Create directory structure")
    
    def cleanup_step_files(self, step_name: str, keep_output: bool = True):
        """
        Clean temporary files of the step
        
        Args:
            step_name: Step name
            keep_output: Keep output file
        """
        step_paths = self.get_step_paths(step_name)
        
        # Clean up intermediate files directory
        if step_paths["intermediate_dir"].exists():
            import shutil
            shutil.rmtree(step_paths["intermediate_dir"])
            logger.info(f"Cleaned steps {step_name} Intermediate file")
        
        # (Optional) Cleans up input files
        if step_paths["input_path"].exists():
            step_paths["input_path"].unlink()
            logger.debug(f"Cleaned steps {step_name} input file")
        
        # (Optional) Cleans up output files
        if not keep_output and step_paths["output_path"].exists():
            step_paths["output_path"].unlink()
            logger.info(f"Cleaned steps {step_name} Output file")
    
    def get_directory_size(self, dir_path: Path) -> int:
        """Gets the size of the directory (in bytes))"""
        total_size = 0
        try:
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"An error occurred while calculating the directory size: {dir_path}, Error: {e}")
        
        return total_size
    
    def get_project_size_info(self) -> Dict[str, Any]:
        """Get project size information"""
        size_info = {}
        
        for dir_name, dir_path in self.directory_structure.items():
            if dir_path.exists():
                size_info[dir_name] = {
                    "path": str(dir_path),
                    "size_bytes": self.get_directory_size(dir_path),
                    "file_count": len(list(dir_path.rglob("*"))) if dir_path.is_dir() else 0
                }
            else:
                size_info[dir_name] = {
                    "path": str(dir_path),
                    "size_bytes": 0,
                    "file_count": 0,
                    "exists": False
                }
        
        return size_info
    
    def validate_paths(self) -> List[str]:
        """Validate path validity"""
        errors = []
        
        # Checks if the project directory is writable
        if not self.project_dir.exists():
            try:
                self.project_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Failed to create project directory: {self.project_dir}, Error: {e}")
        
        # Check all subdirectories
        for dir_name, dir_path in self.directory_structure.items():
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Unable to create directory {dir_name}: {dir_path}, Error: {e}")
            elif not dir_path.is_dir():
                errors.append(f"Path is not a directory: {dir_name} -> {dir_path}")
        
        return errors
    
    def get_relative_path(self, absolute_path: Path) -> str:
        """Obtains a path relative to the project directory"""
        try:
            return str(absolute_path.relative_to(self.project_dir))
        except ValueError:
            return str(absolute_path)
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Get absolute path"""
        return self.project_dir / relative_path 