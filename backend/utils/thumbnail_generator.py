"""
Video Thumbnail Generator Utility
"""
import subprocess
import logging
from pathlib import Path
from typing import Optional
import base64
from PIL import Image
import io
from .ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)

class ThumbnailGenerator:
    """Video thumbnail generator"""
    
    def __init__(self):
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
    
    def generate_thumbnail(self, video_path: Path, output_path: Optional[Path] = None, 
                          time_offset: Optional[float] = None, width: int = 320, height: int = 180) -> Optional[Path]:
        """
        Generate video thumbnail using intelligent frame selection strategy
        
        Args:
            video_path: Path to video file
            output_path: Path to output thumbnail; auto-generated if None
            time_offset: Frame time offset in seconds; auto-selected if None
            width: Thumbnail width
            height: Thumbnail height
            
        Returns:
            Path to generated thumbnail, or None on failure
        """
        try:
            if not video_path.exists():
                logger.error(f"Video file does not exist: {video_path}")
                return None
            
            # Check file format
            if video_path.suffix.lower() not in self.supported_formats:
                logger.error(f"Unsupported video format: {video_path.suffix}")
                return None
            
            # Generate output path
            if output_path is None:
                output_path = video_path.parent / f"{video_path.stem}_thumbnail.jpg"
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Intelligently select timestamp
            if time_offset is None:
                time_offset = self._get_optimal_thumbnail_time(video_path)
            
            # Check whether to use video cover
            if time_offset == -1.0:
                # Use video cover
                cover_path = video_path.parent / f"{video_path.stem}_cover.jpg"
                if cover_path.exists():
                    # Copy cover file and resize directly
                    ffmpeg_bin = get_ffmpeg_path()
                    cmd = [
                        ffmpeg_bin,
                        '-i', str(cover_path),
                        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
                        '-q:v', '2',
                        '-y',
                        str(output_path)
                    ]
                    logger.info(f"Generating thumbnail using video cover: {cover_path} -> {output_path}")
                else:
                    # Cover does not exist, falling back to default timestamp
                    time_offset = 1.0
                    cmd = [
                        'ffmpeg',
                        '-ss', str(time_offset),
                        '-i', str(video_path),
                        '-vframes', '1',
                        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
                        '-q:v', '2',
                        '-y',
                        str(output_path)
                    ]
                    logger.info(f"Cover does not exist, falling back to default timestamp: {time_offset}s")
            else:
                # Use specified timestamp
                logger.info(f"For video {video_path.name} selected thumbnail timestamp: {time_offset}s")
                ffmpeg_bin = get_ffmpeg_path()
                cmd = [
                    ffmpeg_bin,
                    '-ss', str(time_offset),  # Seek to specified time
                    '-i', str(video_path),    # Input video
                    '-vframes', '1',          # Extract single frame
                    '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',  # Scale and pad center
                    '-q:v', '2',              # High quality
                    '-y',                     # Overwrite output file
                    str(output_path)
                ]
            
            logger.info(f"Generating thumbnail: {video_path} -> {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Thumbnail generated successfully: {output_path}")
                return output_path
            else:
                logger.error(f"Thumbnail generation failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Thumbnail generation timed out: {video_path}")
            return None
        except Exception as e:
            logger.error(f"Thumbnail generation exception: {e}")
            return None
    
    def _extract_video_cover(self, video_path: Path) -> Optional[Path]:
        """
        Attempt to extract embedded cover artwork from video
        
        Args:
            video_path: Path to video file
            
        Returns:
            Cover image path, or None if non-existent
        """
        try:
            # Check for embedded cover artwork
            ffmpeg_bin = get_ffmpeg_path()
            cmd = [
                ffmpeg_bin,
                '-i', str(video_path),
                '-an',  # Disable audio
                '-vcodec', 'copy',  # Copy video stream
                '-f', 'image2',
                '-vframes', '1',
                '-y',
                str(video_path.parent / f"{video_path.stem}_cover.jpg")
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                cover_path = video_path.parent / f"{video_path.stem}_cover.jpg"
                if cover_path.exists() and cover_path.stat().st_size > 0:
                    logger.info(f"Successfully extracted video cover: {cover_path}")
                    return cover_path
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to extract video cover: {e}")
            return None
    
    def _get_optimal_thumbnail_time(self, video_path: Path) -> float:
        """
        Intelligently select the optimal thumbnail timestamp
        
        Strategy:
        1. Prioritize extracting embedded video cover if available
        2. If video is short (<30s), select midpoint
        3. If video is medium length (30s-5 minutes), select 10% position
        4. If video is long (>5m), select 5% position
        5. Avoid start/end boundaries to prevent black screens or transitions
        
        Args:
            video_path: Path to video file
            
        Returns:
            Optimal timestamp (seconds)
        """
        try:
            # First attempt to extract video cover
            cover_path = self._extract_video_cover(video_path)
            if cover_path:
                logger.info(f"Using video cover as thumbnail: {cover_path}")
                # If cover extracted, return sentinel value indicating cover usage
                return -1.0  # Sentinel value indicating cover usage
            
            # Get video info
            video_info = self.get_video_info(video_path)
            if not video_info:
                logger.warning(f"Failed to get video info, using default timestamp: {video_path}")
                return 1.0
            
            # Get video duration
            duration = float(video_info.get('format', {}).get('duration', 0))
            if duration <= 0:
                logger.warning(f"Video duration is 0, using default timestamp: {video_path}")
                return 1.0
            
            logger.info(f"Video duration: {duration}s")
            
            # Intelligently select timestamp
            if duration < 30:
                # Short video: select midpoint
                optimal_time = duration * 0.5
            elif duration < 300:  # 5 minutes
                # Medium video: select 10% mark to avoid intro blank frames
                optimal_time = duration * 0.1
            else:
                # Long video: select 5% mark
                optimal_time = duration * 0.05
            
            # Ensure timestamp is reasonable (at least 1s, within video length)
            optimal_time = max(1.0, min(optimal_time, duration - 1))
            
            logger.info(f"For video {video_path.name} selected optimal timestamp: {optimal_time}s (total duration: {duration}s)")
            return optimal_time
            
        except Exception as e:
            logger.error(f"Failed to select optimal timestamp: {e}")
            return 1.0
    
    def generate_thumbnail_base64(self, video_path: Path, time_offset: Optional[float] = None, 
                                 width: int = 320, height: int = 180) -> Optional[str]:
        """
        Generate thumbnail and return base64 string
        
        Args:
            video_path: Path to video file
            time_offset: Frame time offset in seconds; auto-selected if None
            width: Thumbnail width
            height: Thumbnail height
            
        Returns:
            Base64 encoded thumbnail data, or None on failure
        """
        try:
            # Generate temporary thumbnail
            temp_path = video_path.parent / f"temp_thumbnail_{video_path.stem}.jpg"
            thumbnail_path = self.generate_thumbnail(video_path, temp_path, time_offset, width, height)
            
            if thumbnail_path and thumbnail_path.exists():
                # Read image and convert to base64
                with open(thumbnail_path, 'rb') as f:
                    image_data = f.read()
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                
                # Clean up temporary file
                try:
                    temp_path.unlink()
                except:
                    pass
                
                return f"data:image/jpeg;base64,{base64_data}"
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate base64 thumbnail: {e}")
            return None
    
    def get_video_info(self, video_path: Path) -> Optional[dict]:
        """
        Get video metadata
        
        Args:
            video_path: Path to video file
            
        Returns:
            Video metadata dict, or None on failure
        """
        try:
            if not video_path.exists():
                return None
            
            ffprobe_bin = get_ffprobe_path()
            cmd = [
                ffprobe_bin,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                logger.error(f"Failed to get video metadata: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Exception getting video metadata: {e}")
            return None

# Convenience functions
def generate_project_thumbnail(project_id: str, video_path: Path) -> Optional[str]:
    """
    Generate thumbnail for project
    
    Args:
        project_id: Project ID
        video_path: Path to video file
        
    Returns:
        Base64 encoded thumbnail data
    """
    generator = ThumbnailGenerator()
    return generator.generate_thumbnail_base64(video_path)

