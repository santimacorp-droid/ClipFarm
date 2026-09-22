import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from .video_processor import VideoProcessor
from .subtitle_processor import SubtitleProcessor
from .ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)

class VideoEditor:
    """Video Editor - Supports re-editing video based on subtitle deletion"""
    
    def __init__(self, clips_dir: Optional[str] = None, collections_dir: Optional[str] = None):
        # VideoEditor requires explicit paths to avoid global path pollution
        if clips_dir is None or collections_dir is None:
            # If no path provided, use temporary directory (does not affect main pipeline)
            from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR
            clips_dir = str(CLIPS_DIR) if clips_dir is None else clips_dir
            collections_dir = str(COLLECTIONS_DIR) if collections_dir is None else collections_dir
        
        self.video_processor = VideoProcessor(clips_dir=clips_dir, collections_dir=collections_dir)
        self.subtitle_processor = SubtitleProcessor()
    
    def edit_video_by_subtitle_deletion(self, 
                                      video_path: Path,
                                      subtitle_data: List[Dict],
                                      deleted_segments: List[str],
                                      output_path: Path) -> Dict:
        """
        Edit video based on subtitle deletion
        
        Args:
            video_path: Original video path
            subtitle_data: Subtitle data
            deleted_segments: List of subtitle segment IDs to delete
            output_path: Output video path
            
        Returns:
            Edit result information
        """
        try:
            logger.info(f"Starting edit video based on subtitle deletion: {video_path}")
            
            # Generate edited timeline
            timeline = self.subtitle_processor.generate_edited_video_timeline(
                subtitle_data, deleted_segments
            )
            
            if not timeline:
                logger.warning("No retained time range, unable to generate video")
                return {
                    'success': False,
                    'error': 'No retained time range'
                }
            
            # Calculate total deleted duration
            total_deleted_duration = self._calculate_deleted_duration(
                subtitle_data, deleted_segments
            )
            
            # Non-destructive backup of original file if modifying in-place
            if output_path.resolve() == video_path.resolve() or output_path.exists():
                backup_path = video_path.parent / f"{video_path.stem}_backup{video_path.suffix}"
                if not backup_path.exists() and video_path.exists():
                    import shutil
                    try:
                        shutil.copy2(video_path, backup_path)
                        logger.info(f"Created non-destructive backup: {backup_path}")
                    except Exception as b_err:
                        logger.warning(f"Could not create video backup: {b_err}")

            # Executing video editing
            success = self._concatenate_video_segments(
                video_path, timeline, output_path
            )
            
            if success:
                # Getting final video duration
                final_duration = self._get_video_duration(output_path)
                
                result = {
                    'success': True,
                    'originalVideoPath': str(video_path),
                    'editedVideoPath': str(output_path),
                    'totalDeletedDuration': total_deleted_duration,
                    'finalDuration': final_duration,
                    'timeline': timeline,
                    'deletedSegments': deleted_segments
                }
                
                logger.info(f"Video editing completed: deleted duration {total_deleted_duration:.2f}s, "
                          f"final duration {final_duration:.2f}s")
                return result
            else:
                return {
                    'success': False,
                    'error': 'Video cut failed'
                }
                
        except Exception as e:
            logger.error(f"Video editing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_deleted_duration(self, subtitle_data: List[Dict], 
                                  deleted_segments: List[str]) -> float:
        """
        Calculate total deleted duration
        
        Args:
            subtitle_data: Subtitle data
            deleted_segments: List of deleted subtitle segment IDs
            
        Returns:
            Deleted total duration (seconds))
        """
        deleted_ids = set(deleted_segments)
        total_duration = 0.0
        
        for segment in subtitle_data:
            if segment['id'] in deleted_ids:
                duration = segment['endTime'] - segment['startTime']
                total_duration += duration
        
        return total_duration
    
    def _concatenate_video_segments(self, video_path: Path, 
                                  timeline: List[Tuple[float, float]], 
                                  output_path: Path) -> bool:
        """
        Concatenate video segments
        
        Args:
            video_path: Original video path
            timeline: Timeline tuples [(start, end), ...]
            output_path: Output file path
            
        Returns:
            Whether operation succeeded
        """
        try:
            # Ensuring output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if len(timeline) == 1:
                # Only one segment, extract directly
                start_time, end_time = timeline[0]
                return self._extract_single_segment(
                    video_path, start_time, end_time, output_path
                )
            else:
                # Multiple segments, concatenate required
                return self._concatenate_multiple_segments(
                    video_path, timeline, output_path
                )
                
        except Exception as e:
            logger.error(f"Failed to concatenate video segments: {e}")
            return False
    
    def _extract_single_segment(self, video_path: Path, 
                              start_time: float, end_time: float, 
                              output_path: Path) -> bool:
        """
        Extracting individual video segment
        
        Args:
            video_path: Original video path
            start_time: Start time (seconds))
            end_time: End time (seconds))
            output_path: Output file path
            
        Returns:
            Whether operation succeeded
        """
        try:
            duration = end_time - start_time
            if duration <= 0:
                logger.warning(f"Invalid duration {duration} for segment {start_time}->{end_time}")
                return False
            
            ffmpeg_bin = get_ffmpeg_path()
            hw_cfg = VideoProcessor.get_hardware_encoder_config()
            if hw_cfg.get("use_vaapi"):
                cmd = [
                    ffmpeg_bin,
                    *hw_cfg["hw_init"],
                    '-ss', str(start_time),
                    '-i', str(video_path),
                    '-t', str(duration),
                    '-vf', 'format=nv12,hwupload',
                    *hw_cfg["codec_args"],
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    str(output_path)
                ]
            else:
                cmd = [
                    ffmpeg_bin,
                    '-ss', str(start_time),
                    '-i', str(video_path),
                    '-t', str(duration),
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-crf', '22',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    str(output_path)
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"Successfully extracted video segment: {start_time:.2f}s - {end_time:.2f}s")
                return True
            else:
                logger.error(f"Failed to extract video segment: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Exception extracting video segment: {e}")
            return False
    
    def _concatenate_multiple_segments(self, video_path: Path, 
                                     timeline: List[Tuple[float, float]], 
                                     output_path: Path) -> bool:
        """
        Concatenating multiple video segments
        
        Args:
            video_path: Original video path
            timeline: Timeline tuples [(start, end), ...]
            output_path: Output file path
            
        Returns:
            Whether operation succeeded
        """
        try:
            # Creating temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Extracting all segments
                segment_files = []
                for i, (start_time, end_time) in enumerate(timeline):
                    segment_file = temp_path / f"segment_{i:03d}.mp4"
                    
                    success = self._extract_single_segment(
                        video_path, start_time, end_time, segment_file
                    )
                    
                    if success:
                        segment_files.append(segment_file)
                    else:
                        logger.error(f"Extract segment {i} failed")
                        return False
                
                # Creating file list
                file_list_path = temp_path / "file_list.txt"
                with open(file_list_path, 'w', encoding='utf-8') as f:
                    for segment_file in segment_files:
                        f.write(f"file '{segment_file}'\n")
                
                # Concatenate all segments
                ffmpeg_bin = get_ffmpeg_path()
                cmd = [
                    ffmpeg_bin,
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(file_list_path),
                    '-c', 'copy',
                    '-y',
                    str(output_path)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"Successfully concatenated {len(segment_files)} video segments")
                    return True
                else:
                    logger.error(f"Failed to concatenate video segments: {result.stderr}")
                    return False
                    
        except Exception as e:
            logger.error(f"Exception concatenating multiple video segments: {e}")
            return False
    
    def _get_video_duration(self, video_path: Path) -> float:
        """
        Getting video duration
        
        Args:
            video_path: Video file path
            
        Returns:
            Video duration (seconds))
        """
        try:
            ffprobe_bin = get_ffprobe_path()
            cmd = [
                ffprobe_bin,
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration
            else:
                logger.warning(f"Getting video durationfailed: {result.stderr}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Getting video duration failed: {e}")
            return 0.0
    
    def create_preview_clips(self, video_path: Path, 
                           subtitle_data: List[Dict],
                           deleted_segments: List[str],
                           output_dir: Path) -> List[Path]:
        """
        Create preview segment for pre-edit review
        
        Args:
            video_path: Original video path
            subtitle_data: Subtitle data
            deleted_segments: List of subtitle segment IDs to delete
            output_dir: Output directory
            
        Returns:
            List of preview segment file paths
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            preview_files = []
            
            # Create preview for each segment to delete
            for segment_id in deleted_segments:
                segment = next((s for s in subtitle_data if s['id'] == segment_id), None)
                if segment:
                    preview_file = output_dir / f"preview_{segment_id}.mp4"
                    
                    success = self._extract_single_segment(
                        video_path,
                        segment['startTime'],
                        segment['endTime'],
                        preview_file
                    )
                    
                    if success:
                        preview_files.append(preview_file)
            
            logger.info(f"Created {len(preview_files)} preview segments")
            return preview_files
            
        except Exception as e:
            logger.error(f"Creating preview segment failed: {e}")
            return []
    
    def validate_edit_operations(self, subtitle_data: List[Dict], 
                               deleted_segments: List[str]) -> Dict:
        """
        Validate validity of editing operations
        
        Args:
            subtitle_data: Subtitle data
            deleted_segments: List of subtitle segment IDs to delete
            
        Returns:
            Validation result
        """
        try:
            # Check if deleted subtitle segment exists
            existing_ids = {seg['id'] for seg in subtitle_data}
            deleted_ids = set(deleted_segments)
            
            invalid_ids = deleted_ids - existing_ids
            if invalid_ids:
                return {
                    'valid': False,
                    'error': f'Invalid subtitle segmentID: {list(invalid_ids)}'
                }
            
            # Check if remaining content exists after deletion
            remaining_segments = [seg for seg in subtitle_data if seg['id'] not in deleted_ids]
            
            if not remaining_segments:
                return {
                    'valid': False,
                    'error': 'No remaining content after deleting all subtitle segments'
                }
            
            # Calculating deleted duration
            total_deleted_duration = self._calculate_deleted_duration(
                subtitle_data, deleted_segments
            )
            
            # Calculate total duration
            total_duration = max(seg['endTime'] for seg in subtitle_data) - min(seg['startTime'] for seg in subtitle_data)
            
            return {
                'valid': True,
                'totalDuration': total_duration,
                'deletedDuration': total_deleted_duration,
                'remainingDuration': total_duration - total_deleted_duration,
                'deletedSegments': len(deleted_segments),
                'remainingSegments': len(remaining_segments)
            }
            
        except Exception as e:
            logger.error(f"Editing operation validation failed: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
