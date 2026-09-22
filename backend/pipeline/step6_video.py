"""
Step 6: Video Generation - Generate final video clips based on clustering results
"""
import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# Import dependencies
from ..utils.video_processor import VideoProcessor
from ..utils.cta_overlay import apply_cta_overlay, generate_multiplatform_cta_overlays
from ..core.shared_config import METADATA_DIR, CLIPS_DIR, COLLECTIONS_DIR
from ..core import shared_config

logger = logging.getLogger(__name__)


def _ts_to_seconds(ts: Any) -> float:
    """Convert HH:MM:SS, MM:SS, float-string, or float to seconds."""
    if isinstance(ts, (int, float)):
        return float(ts)
    s = str(ts).strip().replace(',', '.')
    parts = s.split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(s)
    except (ValueError, IndexError):
        return 0.0


_parse_timestamp_to_seconds = _ts_to_seconds


class VideoGenerator:
    """Video Generator"""
    
    def __init__(self, clips_dir: Optional[str] = None, collections_dir: Optional[str] = None, metadata_dir: Optional[str] = None, max_clip_duration: float = 600.0):
        # Force use of project-specific directory, do not use global directory as fallback
        if not clips_dir:
            raise ValueError("clips_dir Parameters are required, cannot use global paths")
        if not collections_dir:
            raise ValueError("collections_dir Parameters are required, cannot use global paths")
        
        self.clips_dir = Path(clips_dir)
        self.collections_dir = Path(collections_dir)
        self.metadata_dir = Path(metadata_dir) if metadata_dir else METADATA_DIR
        self.max_clip_duration = max_clip_duration
        
        # Ensure directory exists
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        
        # Create VideoProcessor instance, force using project internal paths
        self.video_processor = VideoProcessor(
            clips_dir=str(self.clips_dir), 
            collections_dir=str(self.collections_dir),
            max_clip_duration=self.max_clip_duration
        )
    
    def generate_clips(self, clips_with_titles: List[Dict], input_video: Path, 
                       srt_path: Optional[Path] = None, 
                       caption_style: str = "hormozi_yellow",
                       show_hook_banner: bool = True,
                       watermark_path: Optional[Path] = None,
                       watermark_position: str = "bottom_right",
                       watermark_scale: float = 15.0,
                       watermark_opacity: float = 0.85,
                       watermark_margin: int = 24,
                       watermark_text: Optional[str] = None,
                       watermark_text_opacity: float = 0.50,
                       watermark_text_position: str = "lower_center",
                       aspect_ratio: str = "9:16_blur",
                       category: str = "general",
                       tracker: Optional[Any] = None) -> List[Path]:
        """
        Generate clip videos, support subtitle generation/Burn subtitles and watermarks

        Args:
            clips_with_titles: Data of fragments with titles
            input_video: Input video path
            srt_path: Optional path of subtitle file
            caption_style: Subtitle style ('hormozi_yellow', 'neon_green', 'neon_cyan', 'clean_box', 'none')
            show_hook_banner: Burn hook title banner at top
            watermark_path: Optional path of watermark logo image
            watermark_position: Watermark position
            watermark_scale: Watermark size percentage
            watermark_opacity: Watermark opacity
            watermark_margin: Watermark margin
            watermark_text: Optional social handle watermark (e.g. '@yourhandle')
            watermark_text_opacity: Opacity for text watermark
            watermark_text_position: Position for text watermark
            aspect_ratio: Aspect ratio ('9:16_blur', '9:16_header', '16:9', etc.)
            category: Content category for theming and hook styling
            tracker: Optional ProgressTracker instance
            
        Returns: list of generated slice video paths
        """
        logger.info(f"Start generating clip videos... (Caption style: {caption_style}, Top Banner: {show_hook_banner}, Watermark: {bool(watermark_path)}, TextWM: {bool(watermark_text)})")
        
        input_video = Path(input_video)
        if srt_path is not None:
            srt_path = Path(srt_path)
        if watermark_path is not None:
            watermark_path = Path(watermark_path)

        # If srt_path is not explicitly provided, try automatically finding in the same directory or raw directory input.srt
        if srt_path is None or not srt_path.exists():
            candidate_srts = [
                input_video.parent / "input.srt",
                input_video.parent.parent / "raw" / "input.srt"
            ]
            for candidate in candidate_srts:
                if candidate.exists():
                    srt_path = candidate
                    logger.info(f"Automatically detect subtitle files: {srt_path}")
                    break
        
        # Prepare clip data
        clips_data = []
        for clip in clips_with_titles:
            clips_data.append({
                'id': clip.get('id'),
                'title': clip.get('generated_title', clip.get('title')),
                'start_time': clip.get('start_time'),
                'end_time': clip.get('end_time'),
                'hook_text': clip.get('hook_text'),
                'hook_title': clip.get('hook_title') or clip.get('hook_text'),
                'category': clip.get('category') or category,
                'recommend_reason': clip.get('recommend_reason'),
                'watermark_text': clip.get('watermark_text') or watermark_text,
                'watermark_text_opacity': clip.get('watermark_text_opacity') or watermark_text_opacity,
                'watermark_text_position': clip.get('watermark_text_position') or watermark_text_position
            })

        # Smart sentence boundary extension for step 6 clips
        if srt_path and srt_path.exists():
            try:
                from ..utils.sentence_boundary_extender import extend_to_sentence_boundary
                for clip in clips_data:
                    raw_end = float(
                        VideoProcessor.convert_srt_time_to_ffmpeg_time(clip['end_time'])
                    )
                    adj_end = extend_to_sentence_boundary(raw_end, srt_words=Path(srt_path), tolerance_sec=12.0)
                    if adj_end > raw_end:
                        logger.info(f"Extended clip {clip.get('id')} end boundary from {raw_end:.2f}s to {adj_end:.2f}s for sentence completion.")
                        clip['end_time'] = VideoProcessor.convert_seconds_to_ffmpeg_time(adj_end)
            except Exception as ext_err:
                logger.debug(f"Sentence boundary extension skipped in generate_clips: {ext_err}")
        
        # Batch generate slices (with subtitle processing, watermarks, and 9:16 vertical screen formatting))
        successful_clips = self.video_processor.batch_extract_clips(
            input_video=input_video, 
            clips_data=clips_data,
            srt_path=srt_path,
            caption_style=caption_style,
            show_hook_banner=show_hook_banner,
            watermark_path=watermark_path,
            watermark_position=watermark_position,
            watermark_scale=watermark_scale,
            watermark_opacity=watermark_opacity,
            watermark_margin=watermark_margin,
            watermark_text=watermark_text,
            watermark_text_opacity=watermark_text_opacity,
            watermark_text_position=watermark_text_position,
            aspect_ratio=aspect_ratio,
            category=category,
            tracker=tracker
        )
        
        # Apply CTA Overlay — main pipeline
        clip_lookup = {str(c.get('id', '')): c for c in clips_with_titles}
        updated_successful_clips = []

        for output_video in successful_clips:
            cid = output_video.stem.split('_')[0]
            clip = clip_lookup.get(cid, {})
            raw_style = clip.get('cta_style')
            cta_style = raw_style if (raw_style and raw_style != 'none') else getattr(shared_config, 'DEFAULT_CTA_STYLE', 'follow_tap')
            cta_platform = clip.get('cta_platform') or getattr(shared_config, 'DEFAULT_CTA_PLATFORM', 'tiktok')
            cta_handle = clip.get('cta_handle', '') or getattr(shared_config, 'DEFAULT_CTA_HANDLE', '')
            cta_position = clip.get('cta_position') or getattr(shared_config, 'DEFAULT_CTA_POSITION', 'lower_center')

            if cta_style and cta_style != 'none' and output_video.exists():
                cta_platforms_map = generate_multiplatform_cta_overlays(
                    input_path=output_video,
                    output_dir=output_video.parent,
                    stem_prefix=output_video.stem,
                    handle=cta_handle,
                    base_style=cta_style,
                    position=cta_position,
                    primary_platform=cta_platform
                )
                cta_output = output_video.parent / f"{output_video.stem}_cta.mp4"
                if cta_platforms_map:
                    primary_file = cta_platforms_map.get(cta_platform) or str(cta_output)
                    if os.path.exists(primary_file):
                        output_video = Path(primary_file)
                    clip['cta_applied'] = True
                    clip['cta_video_file'] = str(cta_output) if cta_output.exists() else str(output_video)
                    clip['cta_platforms'] = cta_platforms_map
                    clip['platform_videos'] = cta_platforms_map
                    clip['cta_style'] = cta_style
                    clip['cta_platform'] = cta_platform
                    logger.info(f"Generated multiplatform CTA overlays for normal clip {cid}: {list(cta_platforms_map.keys())}")

            updated_successful_clips.append(output_video)

        successful_clips = updated_successful_clips
        logger.info(f"Slice video generated successfully, total{len(successful_clips)}clips")
        return successful_clips
    
    def generate_collections(self, collections_data: List[Dict]) -> List[Dict]:
        """
        Generate Compilation Video
        
        Args:
            collections_data: compilation data
            
        Returns:
            List of generated compilation information containing video paths and thumbnail paths
        """
        logger.info("Start generating compilation video...")
        
        # Generate collection video and thumbnail
        successful_collections = self.video_processor.create_collections_from_metadata(collections_data)
        
        logger.info(f"Compilation video generation complete, total{len(successful_collections)}compilations")
        return successful_collections
    
    def save_clip_metadata(self, clips_with_titles: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        Save final clip metadata to clips_metadata.json
        
        Args:
            clips_with_titles: Clip data with titles (from step 4)
            output_path: Output path, default is clips_metadata.json
            
        Returns:
            Saved file path
            
        Note:
            This method saves the final clip metadata, which contains complete information after video generation.
            Unlike step 4's step4_titles.json, it saves the final data for front-end display.. 
        """
        if output_path is None:
            output_path = self.metadata_dir / "clips_metadata.json"
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Attach platform duration advisories
        try:
            from ..core.platform_advisor import get_platform_advisory
            for clip in clips_with_titles:
                try:
                    s_sec = _parse_timestamp_to_seconds(clip.get('start_time', '0'))
                    e_sec = _parse_timestamp_to_seconds(clip.get('end_time', '0'))
                    dur = max(1.0, e_sec - s_sec)
                    clip['platform_advisory'] = get_platform_advisory(dur)
                except Exception as pa_err:
                    logger.debug(f"Could not compute platform advisory for clip {clip.get('id')}: {pa_err}")
        except Exception as adv_mod_err:
            logger.debug(f"Platform advisor unavailable: {adv_mod_err}")
        
        # Save data
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clips_with_titles, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Clip metadata saved to: {output_path}")
        return output_path
    
    def save_collection_metadata(self, collections_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        Save Compilation Metadata
        
        Args:
            collections_data: Compilation data
            output_path: Output path
            
        Returns:
            Saved file path
        """
        if output_path is None:
            output_path = self.metadata_dir / "collections_metadata.json"
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save data
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(collections_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Compilation metadata saved to: {output_path}")
        return output_path

def run_step6_video(clips_with_titles_path: Path, collections_path: Path, input_video: Path,
                   clips_dir: str, collections_dir: str,
                   metadata_dir: Optional[str] = None,
                   output_dir: Optional[Path] = None,
                   srt_path: Optional[Path] = None,
                   caption_style: str = "hormozi_yellow",
                   show_hook_banner: bool = True,
                   watermark_path: Optional[Path] = None,
                   watermark_position: str = "bottom_right",
                   watermark_scale: float = 15.0,
                   watermark_opacity: float = 0.85,
                   watermark_margin: int = 24,
                   watermark_text: Optional[str] = None,
                   watermark_text_opacity: float = 0.50,
                   watermark_text_position: str = "lower_center",
                   aspect_ratio: str = "9:16_blur",
                   category: str = "general",
                   tracker: Optional[Any] = None) -> Dict[str, Any]:
    """
    Run Step 6: Video Generation
    
    Args:
        clips_with_titles_path: Path to clip data with titles
        collections_path: Path to compilation data
        input_video: Input video path
        clips_dir: Output directory for clip videos
        collections_dir: Output directory for compilation videos
        metadata_dir: Output directory for metadata
        output_dir: Output directory
        srt_path: Optional SRT subtitle file path
        caption_style: Caption style ('hormozi_yellow', 'neon_green', 'neon_cyan', 'clean_box', 'none')
        show_hook_banner: Whether to burn a hook title banner on top
        watermark_path: Optional watermark logo image path
        watermark_position: Watermark position
        watermark_scale: Watermark size percentage
        watermark_opacity: Watermark opacity
        watermark_margin: Watermark margin
        watermark_text: Optional handle/text watermark (e.g. '@yourhandle')
        watermark_text_opacity: Text watermark opacity
        watermark_text_position: Text watermark position
        aspect_ratio: Aspect ratio ('9:16_blur', '9:16_header', '16:9', 'original')
        category: Video category
        tracker: Optional ProgressTracker instance
        
    Returns:
        Generation result information
    """
    # Coerce paths
    clips_with_titles_path = Path(clips_with_titles_path)
    collections_path = Path(collections_path)
    input_video = Path(input_video)
    if output_dir is not None:
        output_dir = Path(output_dir)
    if srt_path is not None:
        srt_path = Path(srt_path)
    if watermark_path is not None:
        watermark_path = Path(watermark_path)

    # Load data
    with open(clips_with_titles_path, 'r', encoding='utf-8') as f:
        clips_with_titles = json.load(f)
    
    with open(collections_path, 'r', encoding='utf-8') as f:
        collections_data = json.load(f)
    
    # Create video generator
    generator = VideoGenerator(clips_dir=clips_dir, collections_dir=collections_dir, metadata_dir=metadata_dir)
    
    # Generate clip videos (support subtitle generation, burning, watermark, and 9:16 vertical formatting))
    successful_clips = generator.generate_clips(
        clips_with_titles=clips_with_titles, 
        input_video=input_video,
        srt_path=srt_path,
        caption_style=caption_style,
        show_hook_banner=show_hook_banner,
        watermark_path=watermark_path,
        watermark_position=watermark_position,
        watermark_scale=watermark_scale,
        watermark_opacity=watermark_opacity,
        watermark_margin=watermark_margin,
        watermark_text=watermark_text,
        watermark_text_opacity=watermark_text_opacity,
        watermark_text_position=watermark_text_position,
        aspect_ratio=aspect_ratio,
        category=category,
        tracker=tracker
    )
    
    # Generate Compilation Video
    successful_collections = generator.generate_collections(collections_data)
    
    # Map generated clip paths to clips_with_titles so clips_metadata.json includes video_path
    clip_path_map = {}
    for p in successful_clips:
        cid = p.stem.split('_')[0]
        clip_path_map[cid] = str(p)
    for clip in clips_with_titles:
        cid = str(clip.get('id', ''))
        if cid in clip_path_map:
            clip['video_path'] = clip_path_map[cid]

    # Save metadata to project directory
    # Note: clips_metadata.json is saved here, containing final clip metadata (including video paths))
    # Different from step4_titles.json of step4, which only saves data of fragments with titles
    if metadata_dir:
        project_metadata_dir = Path(metadata_dir)
        generator.save_clip_metadata(clips_with_titles, project_metadata_dir / "clips_metadata.json")
        generator.save_collection_metadata(collections_data, project_metadata_dir / "collections_metadata.json")
    else:
        generator.save_clip_metadata(clips_with_titles)
        generator.save_collection_metadata(collections_data)
    
    # Return result information
    result = {
        'clips_generated': len(successful_clips),
        'collections_generated': len(successful_collections),
        'clip_paths': [str(path) for path in successful_clips],
        'collection_paths': [collection['video_path'] for collection in successful_collections],
        'collection_thumbnails': [collection['thumbnail_path'] for collection in successful_collections if collection['thumbnail_path']],
        'collections_info': successful_collections  # Includes complete collection information
    }
    
    logger.info(f"Video generation complete: {result['clips_generated']}clips, {result['collections_generated']}compilations")
    
    # Save results to output file
    if output_dir is not None:
        output_path = output_dir / "step6_video_output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"Step 6 results saved to: {output_path}")
    
    return result