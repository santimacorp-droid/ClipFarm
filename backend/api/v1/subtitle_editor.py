import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...utils.subtitle_processor import SubtitleProcessor
from ...utils.video_editor import VideoEditor
from ...core.path_utils import get_data_directory, get_projects_directory
from ...core.database import get_db
from ...services.project_service import ProjectService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

# Request and response model
class SubtitleEditRequest(BaseModel):
    project_id: str
    clip_id: str
    deleted_segments: List[str]

class SubtitleEditResponse(BaseModel):
    success: bool
    message: str
    edited_video_path: Optional[str] = None
    deleted_duration: Optional[float] = None
    final_duration: Optional[float] = None

class SubtitleDataResponse(BaseModel):
    segments: List[Dict]
    total_duration: float
    word_count: int
    segment_count: int

class SubtitleSegmentModel(BaseModel):
    id: Optional[str] = None
    startTime: float
    endTime: float
    text: str

class UpdateClipSubtitlesRequest(BaseModel):
    segments: List[SubtitleSegmentModel]
    caption_style: Optional[str] = "hormozi_yellow"
    reburn_video: Optional[bool] = False
    hook_title: Optional[str] = None
    show_hook_banner: Optional[bool] = False
    aspect_ratio: Optional[str] = "9:16"
    dynamic_zoom: Optional[bool] = False
    bgm_track: Optional[str] = None
    bgm_volume: Optional[float] = 0.18
    sfx_enabled: Optional[bool] = False
    custom_bgm_path: Optional[str] = None

class UpdateProjectSubtitlesRequest(BaseModel):
    segments: List[SubtitleSegmentModel]

def _find_project_srt(project_dir: Path) -> Optional[Path]:
    """Find in projectSRTsubtitle file"""
    candidates = [
        project_dir / "raw" / "input.srt",
        project_dir / "metadata" / "input.srt",
        project_dir / "input.srt"
    ]
    for c in candidates:
        if c.exists():
            return c
    # find any.srtfile
    for srt_path in list(project_dir.glob("raw/*.srt")) + list(project_dir.glob("metadata/*.srt")) + list(project_dir.glob("*.srt")):
        if srt_path.exists():
            return srt_path
    return None

def _find_clip_srt(project_dir: Path, clip_id: str) -> Optional[Path]:
    """Finding slice-specific...SRTsubtitle file"""
    clips_dir = project_dir / "output" / "clips"
    if clips_dir.exists():
        srt_files = list(clips_dir.glob(f"{clip_id}_*.srt")) + list(clips_dir.glob(f"{clip_id}.srt"))
        if srt_files:
            return srt_files[0]
    edited_dir = project_dir / "edited_clips"
    if edited_dir.exists():
        edited_srts = list(edited_dir.glob(f"{clip_id}_edited.srt"))
        if edited_srts:
            return edited_srts[0]
    return None

def _find_clip_video(project_dir: Path, clip_id: str) -> Optional[Path]:
    """Find corresponding video file for clip"""
    clips_dir = project_dir / "output" / "clips"
    if clips_dir.exists():
        video_files = list(clips_dir.glob(f"{clip_id}_*.mp4")) + list(clips_dir.glob(f"{clip_id}.mp4"))
        if video_files:
            return video_files[0]
    edited_dir = project_dir / "edited_clips"
    if edited_dir.exists():
        edited_videos = list(edited_dir.glob(f"{clip_id}_edited.mp4"))
        if edited_videos:
            return edited_videos[0]
    return None

def _find_project_video(project_dir: Path) -> Optional[Path]:
    """Find video files in project"""
    video_files = list(project_dir.glob("raw/*.mp4")) + list(project_dir.glob("*.mp4")) + list(project_dir.glob("raw/*.mkv"))
    return video_files[0] if video_files else None

# Dependency injection function
def get_subtitle_processor() -> SubtitleProcessor:
    return SubtitleProcessor()

def get_video_editor() -> VideoEditor:
    # Subtitle editor uses global path as fallback (does not affect mainstream pipeline))
    from ...core.shared_config import CLIPS_DIR, COLLECTIONS_DIR
    return VideoEditor(clips_dir=str(CLIPS_DIR), collections_dir=str(COLLECTIONS_DIR))

def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    """Dependency to get project service."""
    return ProjectService(db)

def _seconds_to_srt_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS,mmm"""
    if seconds is None or seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000.0))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

@router.get("/{project_id}/clips/{clip_id}/subtitles")
async def get_clip_subtitles(
    project_id: str,
    clip_id: str,
    subtitle_processor: SubtitleProcessor = Depends(get_subtitle_processor),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get clip-specific subtitle data"""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        # Get clip information
        from ...models.clip import Clip
        clip = project_service.db.query(Clip).filter(Clip.id == clip_id, Clip.project_id == project_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="fragment does not exist")
        
        projects_dir = get_projects_directory()
        project_dir = projects_dir / project_id
        
        # 1. Prefer searching for slice-specificSRTfile (output/clips/{clip_id}_*.srt)
        clip_srt = _find_clip_srt(project_dir, clip_id)
        if clip_srt and clip_srt.exists():
            subtitle_data = subtitle_processor.parse_srt_to_word_level(clip_srt)
            stats = subtitle_processor.get_subtitle_statistics(subtitle_data)
            return SubtitleDataResponse(
                segments=subtitle_data,
                total_duration=stats.get('totalDuration', 0.0),
                word_count=stats.get('wordCount', 0),
                segment_count=stats.get('segmentCount', len(subtitle_data))
            )

        # 2. If no dedicatedSRT, from original projectSRTExtract and relativize timestamp
        srt_file = _find_project_srt(project_dir)
        if not srt_file or not srt_file.exists():
            return SubtitleDataResponse(
                segments=[],
                total_duration=0.0,
                word_count=0,
                segment_count=0
            )
        
        # Parse subtitle data
        subtitle_data = subtitle_processor.parse_srt_to_word_level(srt_file)
        
        def parse_clip_time(val: Any) -> float:
            if val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                val = val.strip().replace(',', '.')
                parts = val.split(':')
                if len(parts) == 3:
                    try:
                        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                    except ValueError:
                        return 0.0
                elif len(parts) == 2:
                    try:
                        return float(parts[0]) * 60 + float(parts[1])
                    except ValueError:
                        return 0.0
                try:
                    return float(val)
                except ValueError:
                    return 0.0
            return 0.0

        clip_start = parse_clip_time(getattr(clip, 'start_time', 0.0))
        clip_end = parse_clip_time(getattr(clip, 'end_time', 0.0))
        if clip_end <= clip_start:
            clip_end = clip_start + float(getattr(clip, 'duration', 30.0) or 30.0)

        # filter subtitle segments
        clip_subtitles = [
            seg for seg in subtitle_data 
            if seg['startTime'] >= clip_start - 0.5 and seg['endTime'] <= clip_end + 0.5
        ]
        
        # Adjust timestamp relative to clip start (0 start)
        for seg in clip_subtitles:
            seg['startTime'] = max(0.0, seg['startTime'] - clip_start)
            seg['endTime'] = max(0.0, seg['endTime'] - clip_start)
            for word in seg.get('words', []):
                word['startTime'] = max(0.0, word['startTime'] - clip_start)
                word['endTime'] = max(0.0, word['endTime'] - clip_start)
        
        stats = subtitle_processor.get_subtitle_statistics(clip_subtitles)
        
        return SubtitleDataResponse(
            segments=clip_subtitles,
            total_duration=stats.get('totalDuration', clip_end - clip_start),
            word_count=stats.get('wordCount', 0),
            segment_count=stats.get('segmentCount', len(clip_subtitles))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Failed to get subtitle data: {e}")
        logger.error(f"error details: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get subtitle data: {str(e)}")

@router.put("/{project_id}/clips/{clip_id}/subtitles")
async def update_clip_subtitles(
    project_id: str,
    clip_id: str,
    request: UpdateClipSubtitlesRequest,
    project_service: ProjectService = Depends(get_project_service)
):
    """Save and update clip subtitles, optional re-encode of video"""
    try:
        from ...models.clip import Clip
        from ...utils.caption_styles import ViralCaptionGenerator
        from ...utils.video_processor import VideoProcessor

        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        clip = project_service.db.query(Clip).filter(Clip.id == clip_id, Clip.project_id == project_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="slice does not exist")
        
        projects_dir = get_projects_directory()
        project_dir = projects_dir / project_id
        clips_dir = project_dir / "output" / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        
        safe_title = VideoProcessor.sanitize_filename(clip.title or f"clip_{clip_id}")
        clip_srt_path = clips_dir / f"{clip_id}_{safe_title}.srt"
        clip_ass_path = clips_dir / f"{clip_id}_{safe_title}.ass"
        clip_video_path = clips_dir / f"{clip_id}_{safe_title}.mp4"

        # 1. assembleSRTcontent
        srt_lines = []
        for idx, seg in enumerate(request.segments, start=1):
            s_ts = _seconds_to_srt_timestamp(seg.startTime)
            e_ts = _seconds_to_srt_timestamp(seg.endTime)
            text = seg.text.strip()
            if text:
                srt_lines.append(f"{idx}\n{s_ts} --> {e_ts}\n{text}\n")
        
        srt_content = "\n".join(srt_lines) + "\n" if srt_lines else ""
        clip_srt_path.write_text(srt_content, encoding="utf-8")
        logger.info(f"Successfully saved sliceSRTsubtitles / caption: {clip_srt_path}")

        # 2. regenerateASSeffect subtitles
        hook_title = request.hook_title or (clip.title or "Highlight")
        duration = float(clip.duration or 30.0)
        if request.segments:
            duration = max(duration, request.segments[-1].endTime)

        aspect_ratio = request.aspect_ratio or "9:16"
        video_w, video_h = (1080, 1920) if str(aspect_ratio).startswith("9:16") else (1920, 1080)

        ass_success = ViralCaptionGenerator.generate_clip_ass(
            source_srt_path=clip_srt_path,
            clip_start=0.0,
            clip_end=duration,
            output_ass_path=clip_ass_path,
            style_key=request.caption_style or "hormozi_yellow",
            hook_title=hook_title,
            show_hook_banner=request.show_hook_banner or False,
            video_width=video_w,
            video_height=video_h
        )

        # 3. If re-encoding video is requested
        reburned = False
        if request.reburn_video:
            raw_video = _find_project_video(project_dir)
            if raw_video and raw_video.exists():
                start_time_str = clip.start_time if isinstance(clip.start_time, str) else _seconds_to_srt_timestamp(clip.start_time)
                end_time_str = clip.end_time if isinstance(clip.end_time, str) else _seconds_to_srt_timestamp(clip.end_time)
                
                # Re-extract and burn subtitles (supports 9:16 vertical Reel format, dynamic camera movement, BGM ducking, and SFX)
                burn_ok = VideoProcessor.extract_clip(
                    input_video=raw_video,
                    output_path=clip_video_path,
                    start_time=start_time_str,
                    end_time=end_time_str,
                    ass_path=clip_ass_path if (ass_success and clip_ass_path.exists()) else None,
                    aspect_ratio=aspect_ratio,
                    dynamic_zoom=bool(request.dynamic_zoom),
                    bgm_track=request.bgm_track,
                    bgm_volume=float(request.bgm_volume or 0.18),
                    sfx_enabled=bool(request.sfx_enabled),
                    custom_bgm_path=request.custom_bgm_path
                )
                if burn_ok:
                    reburned = True
                    logger.info(f"Re-burned clip video ({aspect_ratio}): {clip_video_path}")
                    # Update database video_path
                    clip.video_path = str(clip_video_path)
                    project_service.db.commit()

        return {
            "success": True,
            "message": "Captions saved successfully" + (" and video re-rendered" if reburned else ""),
            "clip_id": clip_id,
            "reburned": reburned,
            "srt_path": str(clip_srt_path),
            "ass_path": str(clip_ass_path)
        }

    except Exception as e:
        import traceback
        logger.error(f"Failed to save subtitles: {e}")
        logger.error(f"Details: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to save subtitles: {str(e)}")


@router.post("/upload-bgm")
async def upload_custom_bgm(file: UploadFile = File(...)):
    """Upload custom background music file (MP3, WAV, M4A, OGG, AAC, FLAC)"""
    try:
        from ...utils.audio_enhancer import AudioEnhancer
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
            
        ext = Path(file.filename).suffix.lower()
        if ext not in ['.mp3', '.wav', '.m4a', '.ogg', '.aac', '.flac']:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}. Please upload MP3/WAV/M4A/AAC file")
            
        contents = await file.read()
        if len(contents) < 100:
            raise HTTPException(status_code=400, detail="Audio file is empty or too small")
            
        track_info = AudioEnhancer.save_custom_bgm(contents, file.filename)
        return {"success": True, "message": "Background music uploaded successfully", "track": track_info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload custom BGM: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/bgm-tracks")
async def get_bgm_tracks():
    """Get system-supported background music(BGM)Preset vs user-defined audio tracks list"""
    try:
        from ...utils.audio_enhancer import AudioEnhancer
        tracks = AudioEnhancer.get_available_bgm_tracks()
        return {"success": True, "tracks": tracks}
    except Exception as e:
        logger.error(f"fetch / retrieveBGMlist failed: {e}")
        return {"success": False, "tracks": []}

@router.get("/{project_id}/clips/{clip_id}/export-srt")
async def export_clip_srt(
    project_id: str,
    clip_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """exporting theSRTsubtitle file"""
    try:
        projects_dir = get_projects_directory()
        project_dir = projects_dir / project_id
        clip_srt = _find_clip_srt(project_dir, clip_id)
        if not clip_srt or not clip_srt.exists():
            raise HTTPException(status_code=404, detail="Sliced subtitle file does not exist")
        return FileResponse(
            path=str(clip_srt),
            media_type="text/plain",
            filename=clip_srt.name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exporting sliced subtitles failed: {e}")
        raise HTTPException(status_code=500, detail=f"Exporting sliced subtitles failed: {str(e)}")

@router.post("/{project_id}/clips/{clip_id}/edit")
async def edit_clip_by_subtitles(
    project_id: str,
    clip_id: str,
    request: SubtitleEditRequest,
    subtitle_processor: SubtitleProcessor = Depends(get_subtitle_processor),
    video_editor: VideoEditor = Depends(get_video_editor),
    project_service: ProjectService = Depends(get_project_service)
):
    """Edit and trim video segment based on deleted subtitles"""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        # Get clip information
        from ...models.clip import Clip
        clip = project_service.db.query(Clip).filter(Clip.id == clip_id, Clip.project_id == project_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="fragment does not exist")
        
        # Get original video and subtitle file paths
        projects_dir = get_projects_directory()
        project_dir = projects_dir / project_id
        
        # Find source video file
        original_video = _find_project_video(project_dir)
        if not original_video or not original_video.exists():
            raise HTTPException(status_code=404, detail="Source video file does not exist")
        
        # Find subtitle files
        srt_file = _find_project_srt(project_dir)
        if not srt_file or not srt_file.exists():
            raise HTTPException(status_code=404, detail="Subtitle file does not exist")
        
        # Parse subtitle data
        subtitle_data = subtitle_processor.parse_srt_to_word_level(srt_file)
        
        # Filter out segments within current segment duration
        # ifstart_timeandend_timeIs integer (seconds), direct use directly
        if isinstance(clip.start_time, int):
            clip_start = clip.start_time
        else:
            clip_start = subtitle_processor._srt_time_to_seconds(
                subtitle_processor._seconds_to_srt_time_object(clip.start_time)
            )
        
        if isinstance(clip.end_time, int):
            clip_end = clip.end_time
        else:
            clip_end = subtitle_processor._srt_time_to_seconds(
                subtitle_processor._seconds_to_srt_time_object(clip.end_time)
            )
        
        clip_subtitles = [
            seg for seg in subtitle_data 
            if seg['startTime'] >= clip_start and seg['endTime'] <= clip_end
        ]
        
        # Validate edit operation
        validation = video_editor.validate_edit_operations(
            clip_subtitles, request.deleted_segments
        )
        
        if not validation['valid']:
            raise HTTPException(status_code=400, detail=validation['error'])
        
        # Create output directory
        output_dir = project_dir / "edited_clips"
        output_dir.mkdir(exist_ok=True)
        
        # Generate edited video file name
        edited_video_name = f"{clip_id}_edited.mp4"
        edited_video_path = output_dir / edited_video_name
        
        # Execute video editing
        edit_result = video_editor.edit_video_by_subtitle_deletion(
            original_video,
            clip_subtitles,
            request.deleted_segments,
            edited_video_path
        )
        
        if not edit_result['success']:
            raise HTTPException(status_code=500, detail=f"Video editing failed: {edit_result['error']}")
        
        # Export edited subtitle file
        edited_srt_path = output_dir / f"{clip_id}_edited.srt"
        subtitle_processor.export_edited_srt(
            clip_subtitles,
            request.deleted_segments,
            edited_srt_path
        )
        
        return SubtitleEditResponse(
            success=True,
            message="Video editing succeeded",
            edited_video_path=str(edited_video_path),
            deleted_duration=edit_result['totalDeletedDuration'],
            final_duration=edit_result['finalDuration']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Editing video segment failed: {e}")
        raise HTTPException(status_code=500, detail=f"Editing video segment failed: {str(e)}")

@router.get("/{project_id}/clips/{clip_id}/edited-video")
async def get_edited_video(
    project_id: str,
    clip_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get edited video file"""
    try:
        # Check if project exists
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        # Locate edited video file
        projects_dir = get_projects_directory()
        edited_video_path = projects_dir / project_id / "edited_clips" / f"{clip_id}_edited.mp4"
        
        if not edited_video_path.exists():
            raise HTTPException(status_code=404, detail="Edited video file does not exist")
        
        # Return video file
        return FileResponse(
            path=str(edited_video_path),
            media_type="video/mp4",
            filename=f"{clip_id}_edited.mp4"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get edited video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get edited video: {str(e)}")

@router.post("/{project_id}/clips/{clip_id}/preview")
async def create_edit_preview(
    project_id: str,
    clip_id: str,
    request: EditPreviewRequest,
    subtitle_processor: SubtitleProcessor = Depends(get_subtitle_processor),
    video_editor: VideoEditor = Depends(get_video_editor),
    project_service: ProjectService = Depends(get_project_service)
):
    """Create edit preview clip"""
    try:
        # Get project information
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        # Get clip information
        from ...models.clip import Clip
        clip = project_service.db.query(Clip).filter(Clip.id == clip_id, Clip.project_id == project_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="fragment does not exist")
        
        # Get original video and subtitle file paths
        projects_dir = get_projects_directory()
        project_dir = projects_dir / project_id
        
        original_video = _find_project_video(project_dir)
        if not original_video or not original_video.exists():
            raise HTTPException(status_code=404, detail="Source video file does not exist")
        
        srt_file = _find_project_srt(project_dir)
        if not srt_file or not srt_file.exists():
            raise HTTPException(status_code=404, detail="Subtitle file does not exist")
        
        # Parse subtitle data
        subtitle_data = subtitle_processor.parse_srt_to_word_level(srt_file)
        
        # Filter out segments within current segment duration
        # ifstart_timeandend_timeIs integer (seconds), direct use directly
        if isinstance(clip.start_time, int):
            clip_start = clip.start_time
        else:
            clip_start = subtitle_processor._srt_time_to_seconds(
                subtitle_processor._seconds_to_srt_time_object(clip.start_time)
            )
        
        if isinstance(clip.end_time, int):
            clip_end = clip.end_time
        else:
            clip_end = subtitle_processor._srt_time_to_seconds(
                subtitle_processor._seconds_to_srt_time_object(clip.end_time)
            )
        
        clip_subtitles = [
            seg for seg in subtitle_data 
            if seg['startTime'] >= clip_start and seg['endTime'] <= clip_end
        ]
        
        # Create preview directory
        preview_dir = project_dir / "edit_previews" / clip_id
        preview_dir.mkdir(parents=True, exist_ok=True)
        
        # create preview fragment
        preview_files = video_editor.create_preview_clips(
            original_video,
            clip_subtitles,
            request.deleted_segments,
            preview_dir
        )
        
        return {
            "success": True,
            "preview_files": [str(f) for f in preview_files],
            "count": len(preview_files)
        }
        
    except Exception as e:
        logger.error(f"Failed to create edit preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create edit preview: {str(e)}")

@router.get("/{project_id}/clips/{clip_id}/preview/{segment_id}")
async def get_preview_segment(
    project_id: str,
    clip_id: str,
    segment_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get preview fragment file"""
    try:
        # Check if project exists
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        # Find preview file
        projects_dir = get_projects_directory()
        preview_file = projects_dir / project_id / "edit_previews" / clip_id / f"preview_{segment_id}.mp4"
        
        if not preview_file.exists():
            raise HTTPException(status_code=404, detail="Preview file does not exist")
        
        # Return preview file
        return FileResponse(
            path=str(preview_file),
            media_type="video/mp4",
            filename=f"preview_{segment_id}.mp4"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preview file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get preview file: {str(e)}")
@router.get("/{project_id}/subtitles")
async def get_project_subtitles(
    project_id: str,
    subtitle_processor: SubtitleProcessor = Depends(get_subtitle_processor),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get full projectSRTsubtitle data"""
    try:
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        projects_dir = get_projects_directory()
        project_dir = projects_dir / project_id
        srt_file = _find_project_srt(project_dir)
        
        if not srt_file or not srt_file.exists():
            return SubtitleDataResponse(
                segments=[],
                total_duration=0.0,
                word_count=0,
                segment_count=0
            )
        
        subtitle_data = subtitle_processor.parse_srt_to_word_level(srt_file)
        stats = subtitle_processor.get_subtitle_statistics(subtitle_data)
        
        return SubtitleDataResponse(
            segments=subtitle_data,
            total_duration=stats.get('totalDuration', 0.0),
            word_count=stats.get('wordCount', 0),
            segment_count=stats.get('segmentCount', len(subtitle_data))
        )
    except Exception as e:
        logger.error(f"Failed to get project subtitles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project subtitles: {str(e)}")

@router.put("/{project_id}/subtitles")
async def update_project_subtitles(
    project_id: str,
    request: UpdateProjectSubtitlesRequest,
    project_service: ProjectService = Depends(get_project_service)
):
    """Save and update complete project SRT subtitles"""
    try:
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="project does not exist")
        
        projects_dir = get_projects_directory()
        project_dir = projects_dir / project_id
        srt_file = _find_project_srt(project_dir) or (project_dir / "raw" / "input.srt")
        srt_file.parent.mkdir(parents=True, exist_ok=True)
        
        srt_lines = []
        for idx, seg in enumerate(request.segments, start=1):
            s_ts = _seconds_to_srt_timestamp(seg.startTime)
            e_ts = _seconds_to_srt_timestamp(seg.endTime)
            text = seg.text.strip()
            if text:
                srt_lines.append(f"{idx}\n{s_ts} --> {e_ts}\n{text}\n")
        
        srt_content = "\n".join(srt_lines) + "\n" if srt_lines else ""
        srt_file.write_text(srt_content, encoding="utf-8")
        
        return {
            "success": True,
            "message": "Project subtitles updated successfully",
            "count": len(request.segments)
        }
    except Exception as e:
        logger.error(f"Failed to update project subtitles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update project subtitles: {str(e)}")
