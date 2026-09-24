"""
SliceAPIRoute
"""

from typing import List, Optional
import os
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...services.clip_service import ClipService
from ...schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipStatus, ClipFilter
from ...schemas.base import PaginationParams
from ...models.clip import Clip
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_clip_service(db: Session = Depends(get_db)) -> ClipService:
    """Dependency to get clip service."""
    return ClipService(db)


@router.patch("/{clip_id}/title", response_model=ClipResponse)
async def update_clip_title(
    clip_id: str,
    title_data: dict,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Update clip title."""
    try:
        new_title = title_data.get("title", "").strip()
        if not new_title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        
        if len(new_title) > 200:
            raise HTTPException(status_code=400, detail="Title length cannot exceed200characters")
        
        # Update slice title
        clip = clip_service.update_clip(clip_id, ClipUpdate(title=new_title))
        if not clip:
            raise HTTPException(status_code=404, detail="Slice does not exist")
        
        # Return updated slice information
        return ClipResponse(
            id=str(clip.id),
            project_id=str(clip.project_id),
            title=str(clip.title),
            description=str(clip.description) if clip.description else None,
            start_time=getattr(clip, 'start_time', 0),
            end_time=getattr(clip, 'end_time', 0),
            duration=int(getattr(clip, 'duration', 0)),
            score=getattr(clip, 'score', None),
            status=getattr(clip, 'status', 'pending'),
            video_path=getattr(clip, 'video_path', None),
            tags=getattr(clip, 'tags', []) or [],
            clip_metadata=getattr(clip, 'clip_metadata', {}) or {},
            platform_advisory=getattr(clip, 'platform_advisory', None),
            social_copy=getattr(clip, 'social_copy', None) or ((getattr(clip, 'clip_metadata', {}) or {}).get('social_copy')),
            created_at=getattr(clip, 'created_at', None),
            updated_at=getattr(clip, 'updated_at', None),
            collection_ids=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update slice title failed: {e}")
        raise HTTPException(status_code=500, detail=f"Update slice title failed: {str(e)}")


@router.post("/{clip_id}/generate-title", response_model=dict)
async def generate_clip_title(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Generate a new title for a clip using LLM."""
    try:
        # Get slice info
        clip = clip_service.get(clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail="Slice does not exist")
        
        # Directly fromclip_metadataGet content, do not fetch from file system
        clip_metadata = getattr(clip, 'clip_metadata', {}) or {}
        
        if not clip_metadata:
            raise HTTPException(status_code=404, detail="Slice metadata does not exist")
        
        # PrepareLLMInput data
        llm_input = [{
            "id": clip_id,
            "title": clip_metadata.get('outline', '') or getattr(clip, 'title', ''),
            "content": clip_metadata.get('content', []),
            "recommend_reason": clip_metadata.get('recommend_reason', '')
        }]
        
        # InvocationLLMGenerate title
        from ...utils.llm_client import LLMClient
        from ...core.shared_config import PROMPT_FILES
        
        llm_client = LLMClient()
        
        # Load title generation prompt words
        with open(PROMPT_FILES['title'], 'r', encoding='utf-8') as f:
            title_prompt = f.read()
        
        # InvocationLLM
        raw_response = llm_client.call_with_retry(title_prompt, llm_input)
        
        if not raw_response:
            raise HTTPException(status_code=500, detail="LLMCall failed")
        
        # ParseLLMResponse
        titles_map = llm_client.parse_json_response(raw_response)
        
        if not isinstance(titles_map, dict) or clip_id not in titles_map:
            raise HTTPException(status_code=500, detail="LLMReturn format error")
        
        val = titles_map[clip_id]
        if isinstance(val, dict):
            generated_title = val.get("title", "")
            hook_text = val.get("hook", "")
        else:
            generated_title = str(val)
            hook_text = ""

        return {
            "clip_id": clip_id,
            "generated_title": generated_title,
            "hook_text": hook_text,
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate slice title failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generate slice title failed: {str(e)}")


@router.post("/", response_model=ClipResponse)
async def create_clip(
    clip_data: ClipCreate,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Create a new clip."""
    try:
        clip = clip_service.create_clip(clip_data)
        # Convert to response schema
        status_obj = getattr(clip, 'status', None)
        status_value = status_obj.value if hasattr(status_obj, 'value') else 'pending'
        
        return ClipResponse(
            id=str(getattr(clip, 'id', '')),
            project_id=str(getattr(clip, 'project_id', '')),
            title=str(getattr(clip, 'title', '')),
            description=str(getattr(clip, 'description', '')) if getattr(clip, 'description', None) else None,
            start_time=getattr(clip, 'start_time', 0),
            end_time=getattr(clip, 'end_time', 0),
            duration=getattr(clip, 'duration', 0),
            score=getattr(clip, 'score', None),
            status=status_value,
            video_path=getattr(clip, 'video_path', None),
            tags=getattr(clip, 'tags', []) or [],
            clip_metadata=getattr(clip, 'clip_metadata', {}) or {},
            platform_advisory=getattr(clip, 'platform_advisory', None),
            social_copy=getattr(clip, 'social_copy', None) or ((getattr(clip, 'clip_metadata', {}) or {}).get('social_copy')),
            created_at=getattr(clip, 'created_at', None) if isinstance(getattr(clip, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
            updated_at=getattr(clip, 'updated_at', None) if isinstance(getattr(clip, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
            collection_ids=[]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=ClipListResponse)
async def get_clips(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status: Optional[ClipStatus] = Query(None, description="Filter by status"),
    clip_service: ClipService = Depends(get_clip_service)
):
    """Get paginated clips with optional filtering."""
    try:
        pagination = PaginationParams(page=page, size=size)
        
        filters = None
        if project_id or status:
            filters = ClipFilter(
                project_id=project_id,
                status=status
            )
        
        return clip_service.get_clips_paginated(pagination, filters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.api_route("/{clip_id}/video", methods=["GET", "HEAD"])
async def get_clip_video(
    clip_id: str,
    platform: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    clip_service: ClipService = Depends(get_clip_service)
):
    """Stream a clip's MP4 file to the browser with correct MIME type."""
    from ...core.path_utils import find_clip_video_file

    clip = db.query(Clip).filter_by(id=clip_id).first()
    if not clip:
        clip = clip_service.get(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    metadata = getattr(clip, 'clip_metadata', {}) or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    target_video_path = None

    # Step 1: If specific platform requested, check cta_platforms
    if platform:
        plat_key = str(platform).lower().replace("-", "_").strip()
        cta_plats = metadata.get("cta_platforms") or metadata.get("platform_videos") or {}
        if isinstance(cta_plats, dict):
            cand = cta_plats.get(plat_key)
            if not cand and plat_key in ("youtube", "shorts", "yt"):
                cand = cta_plats.get("youtube_shorts") or cta_plats.get("youtube")
            if not cand and plat_key in ("ig", "reels"):
                cand = cta_plats.get("instagram")
            if not cand and plat_key in ("fb",):
                cand = cta_plats.get("facebook")
            if cand and os.path.exists(cand) and os.path.getsize(cand) > 0:
                target_video_path = cand

    # Step 2: If no platform requested or not found, check cta_video_file
    if not target_video_path:
        cta_f = metadata.get("cta_video_file")
        if cta_f and os.path.exists(cta_f) and os.path.getsize(cta_f) > 0:
            target_video_path = cta_f

    # Step 3: Fallback to regular clip cut video
    if not target_video_path:
        video_path = getattr(clip, 'file_path', None) or getattr(clip, 'video_path', None)
        if not video_path or not os.path.exists(video_path):
            file_path, found_clip = find_clip_video_file(clip.project_id if clip else None, clip_id, clip_obj=clip, db=db)
            if file_path and file_path.exists():
                video_path = str(file_path)
        target_video_path = video_path

    if not target_video_path or not os.path.exists(target_video_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    if os.path.getsize(target_video_path) == 0:
        raise HTTPException(status_code=404, detail="Video file is empty (0 bytes)")

    return FileResponse(
        path=str(target_video_path),
        media_type="video/mp4",
        filename=os.path.basename(target_video_path),
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.api_route("/{clip_id}/download", methods=["GET", "HEAD"])
async def download_clip(
    clip_id: str,
    platform: Optional[str] = Query(None),
    clip_service: ClipService = Depends(get_clip_service)
):
    """Download a clip video file as attachment."""
    import urllib.parse
    from ...core.path_utils import find_clip_video_file
    from ...utils.video_processor import VideoProcessor

    clip = clip_service.get(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    metadata = getattr(clip, 'clip_metadata', {}) or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    target_video_path = None

    if platform:
        plat_key = str(platform).lower().replace("-", "_").strip()
        cta_plats = metadata.get("cta_platforms") or metadata.get("platform_videos") or {}
        if isinstance(cta_plats, dict) and plat_key in cta_plats:
            cand = cta_plats[plat_key]
            if cand and os.path.exists(cand) and os.path.getsize(cand) > 0:
                target_video_path = Path(cand)

    if not target_video_path:
        cta_f = metadata.get("cta_video_file")
        if cta_f and os.path.exists(cta_f) and os.path.getsize(cta_f) > 0:
            target_video_path = Path(cta_f)

    if not target_video_path:
        file_path, clip = find_clip_video_file(clip.project_id if clip else None, clip_id, clip_obj=clip, db=clip_service.db)
        if file_path and file_path.exists():
            target_video_path = file_path

    if not target_video_path or not target_video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    clip_title = (clip.title if clip else None) or getattr(clip, 'generated_title', None) or target_video_path.stem or f"clip_{clip_id}"
    safe_name = VideoProcessor.sanitize_filename(clip_title)
    plat_suffix = f"_{platform.lower()}" if platform else ""
    filename = f"{safe_name}{plat_suffix}.mp4"
    encoded_filename = urllib.parse.quote(filename.encode('utf-8'))

    return FileResponse(
        path=str(target_video_path),
        filename=filename,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@router.post("/{clip_id}/reveal")
async def reveal_clip_in_folder(
    clip_id: str,
    platform: Optional[str] = Query(None),
    clip_service: ClipService = Depends(get_clip_service)
):
    """Reveal the clip video file in native OS file manager (Finder / Explorer / Nautilus)."""
    from ...core.path_utils import find_clip_video_file, get_project_directory, reveal_in_file_manager

    clip = clip_service.get(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    metadata = getattr(clip, 'clip_metadata', {}) or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    target_video_path = None
    if platform:
        plat_key = str(platform).lower().replace("-", "_").strip()
        cta_plats = metadata.get("cta_platforms") or metadata.get("platform_videos") or {}
        if isinstance(cta_plats, dict) and plat_key in cta_plats:
            cand = cta_plats[plat_key]
            if cand and os.path.exists(cand) and os.path.getsize(cand) > 0:
                target_video_path = Path(cand)

    if not target_video_path:
        cta_f = metadata.get("cta_video_file")
        if cta_f and os.path.exists(cta_f) and os.path.getsize(cta_f) > 0:
            target_video_path = Path(cta_f)

    if not target_video_path:
        file_path, _ = find_clip_video_file(clip.project_id if clip else None, clip_id, clip_obj=clip, db=clip_service.db)
        if file_path and file_path.exists():
            target_video_path = file_path

    if not target_video_path or not target_video_path.exists():
        # Fall back to project directory
        proj_dir = get_project_directory(clip.project_id)
        if proj_dir.exists():
            target_video_path = proj_dir
        else:
            raise HTTPException(status_code=404, detail="Clip file not found on disk")

    success = reveal_in_file_manager(target_video_path)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to open system file explorer")
    return {"success": True, "path": str(target_video_path)}


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Get a clip by ID."""
    try:
        clip = clip_service.get(clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        return clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: str,
    clip_data: ClipUpdate,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Update a clip."""
    try:
        clip = clip_service.update_clip(clip_id, clip_data)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        return clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{clip_id}")
async def delete_clip(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Delete a clip."""
    try:
        success = clip_service.delete(clip_id)
        if not success:
            raise HTTPException(status_code=404, detail="Clip not found")
        return {"message": "Clip deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cleanup-duplicates")
async def cleanup_duplicate_clips(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Clean duplicate slice data in project"""
    try:
        from ...models.project import Project
        import json
        from pathlib import Path
        from ...core.config import get_data_directory
        
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Get all slices from database
        db_clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        logger.info(f"There is in database {len(db_clips)} slice of")
        
        # Read original data from file system
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        clips_metadata_file = project_dir / "metadata" / "clips_metadata.json"
        
        if not clips_metadata_file.exists():
            raise HTTPException(status_code=404, detail="Slice metadata file does not exist")
        
        with open(clips_metadata_file, 'r', encoding='utf-8') as f:
            original_clips = json.load(f)
        
        logger.info(f"There is in file system {len(original_clips)} slice of")
        
        # Create an original slice ofIDMapping
        original_clip_ids = {clip['id']: clip for clip in original_clips}
        
        # Clean duplicate data
        deleted_count = 0
        kept_count = 0
        
        for db_clip in db_clips:
            metadata = db_clip.clip_metadata or {}
            original_id = metadata.get('id')
            
            if original_id and original_id in original_clip_ids:
                # This slice is valid, keep
                kept_count += 1
                logger.info(f"Keep slice: {db_clip.title} (ID: {original_id})")
            else:
                # This slice is duplicate or invalid, delete
                logger.info(f"Delete duplicate slices: {db_clip.title} (DB ID: {db_clip.id})")
                db.delete(db_clip)
                deleted_count += 1
        
        db.commit()
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "original_count": len(original_clips),
            "db_before_count": len(db_clips),
            "kept_count": kept_count,
            "deleted_count": deleted_count,
            "message": f"Cleanup complete: kept {kept_count} , deleted {deleted_count} duplicate slices"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cleanup duplicate slices failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Cleaning failed: {str(e)}")


@router.post("/resync-project")
async def resync_project_clips(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Resync project slice data"""
    try:
        from ...models.project import Project
        from ...services.data_sync_service import DataSyncService
        from pathlib import Path
        from ...core.config import get_data_directory
        
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project does not exist")
        
        # Delete existing slice data
        existing_clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        deleted_count = len(existing_clips)
        for clip in existing_clips:
            db.delete(clip)
        db.commit()
        logger.info(f"Deleted {deleted_count} existing slices")
        
        # Resync data
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        sync_service = DataSyncService(db)
        synced_count = sync_service._sync_clips_from_filesystem(project_id, project_dir)
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "deleted_count": deleted_count,
            "synced_count": synced_count,
            "message": f"Resync complete: deleted {deleted_count} count, sync {synced_count} slice of"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resync slice failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Resync failed: {str(e)}")


@router.post("/{clip_id}/social-caption", response_model=dict)
async def generate_clip_social_caption(
    clip_id: str,
    payload: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    """
    Generate or regenerate rich, dual-context social media posting caption and hashtags for a clip.
    Grounds the caption in both the clip's local dialogue and the whole video's overarching outline/topic.
    """
    try:
        from ...models.project import Project
        from ...core.path_utils import get_project_directory
        from ...utils.social_caption_generator import SocialCaptionGenerator
        import json

        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="Clip does not exist")

        project = db.query(Project).filter(Project.id == clip.project_id).first()
        project_dir = get_project_directory(clip.project_id)
        metadata_dir = project_dir / "metadata"

        # Load global context (outlines, project title, category)
        outlines = []
        if (metadata_dir / "step1_outline.json").exists():
            try:
                with open(metadata_dir / "step1_outline.json", "r", encoding="utf-8") as f:
                    outlines = json.load(f)
            except Exception:
                pass

        srt_path = None
        for cand in [metadata_dir / "input.srt", project_dir / "raw" / "input.srt"]:
            if cand.exists():
                srt_path = cand
                break

        category = (payload or {}).get("category") or (clip.clip_metadata or {}).get("category") or (project.category if project else "general")
        model = (payload or {}).get("model")

        global_context = {
            "video_title": project.name if project else "Full Video",
            "video_category": category,
            "project_name": project.name if project else "Full Video",
            "outlines": outlines
        }

        def _format_srt_time(sec: float) -> str:
            sf = float(sec or 0.0)
            h = int(sf // 3600)
            m = int((sf % 3600) // 60)
            s = int(sf % 60)
            ms = int((sf - int(sf)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        # Build clip data dictionary
        clip_data = {
            "id": str(clip.id),
            "title": clip.title,
            "generated_title": clip.title,
            "hook_text": (clip.clip_metadata or {}).get("hook_text") or (clip.clip_metadata or {}).get("hook_title") or clip.title,
            "category": category,
            "start_time": _format_srt_time(float(clip.start_time or 0)),
            "end_time": _format_srt_time(float(clip.end_time or 0)),
            "content": (clip.clip_metadata or {}).get("content", []),
            "recommend_reason": clip.description or (clip.clip_metadata or {}).get("recommend_reason", "")
        }

        generator = SocialCaptionGenerator()
        social_copy = generator.generate_social_caption(
            clip_data=clip_data,
            global_context=global_context,
            srt_path=srt_path,
            model=model
        )

        # Update clip metadata and commit
        if not clip.clip_metadata or not isinstance(clip.clip_metadata, dict):
            clip.clip_metadata = {}
        new_meta = dict(clip.clip_metadata)
        new_meta["social_copy"] = social_copy
        new_meta["post_caption"] = social_copy.get("post_caption")
        new_meta["hashtags"] = social_copy.get("hashtags", [])
        clip.clip_metadata = new_meta
        db.commit()

        # Also update step4_titles.json if it exists
        titles_file = metadata_dir / "step4_titles.json"
        if titles_file.exists():
            try:
                with open(titles_file, "r", encoding="utf-8") as f:
                    titles_list = json.load(f)
                orig_id = (clip.clip_metadata or {}).get("id") or str(clip.id)
                for c in titles_list:
                    if str(c.get("id")) == str(orig_id) or str(c.get("id")) == str(clip.id):
                        c["social_copy"] = social_copy
                        c["post_caption"] = social_copy.get("post_caption")
                        c["hashtags"] = social_copy.get("hashtags", [])
                        break
                with open(titles_file, "w", encoding="utf-8") as f:
                    json.dump(titles_list, f, ensure_ascii=False, indent=2)
            except Exception as fe:
                logger.debug(f"Failed to update step4_titles.json with new social copy: {fe}")

        return {
            "clip_id": str(clip.id),
            "social_copy": social_copy,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate social caption failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Generate social caption failed: {str(e)}")


@router.patch("/{clip_id}/social-caption", response_model=dict)
async def update_clip_social_caption(
    clip_id: str,
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Save custom user modifications to social copy (captions, platform variants, hashtags).
    """
    try:
        from ...core.path_utils import get_project_directory
        import json

        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="Clip does not exist")

        social_copy = payload.get("social_copy")
        if not social_copy or not isinstance(social_copy, dict):
            raise HTTPException(status_code=400, detail="Invalid social_copy data")

        if not clip.clip_metadata or not isinstance(clip.clip_metadata, dict):
            clip.clip_metadata = {}
        new_meta = dict(clip.clip_metadata)
        new_meta["social_copy"] = social_copy
        if social_copy.get("post_caption"):
            new_meta["post_caption"] = social_copy.get("post_caption")
        if social_copy.get("hashtags"):
            new_meta["hashtags"] = social_copy.get("hashtags")
        clip.clip_metadata = new_meta
        db.commit()

        # Update step4_titles.json on disk if present
        try:
            project_dir = get_project_directory(clip.project_id)
            titles_file = project_dir / "metadata" / "step4_titles.json"
            if titles_file.exists():
                with open(titles_file, "r", encoding="utf-8") as f:
                    titles_list = json.load(f)
                orig_id = (clip.clip_metadata or {}).get("id") or str(clip.id)
                for c in titles_list:
                    if str(c.get("id")) == str(orig_id) or str(c.get("id")) == str(clip.id):
                        c["social_copy"] = social_copy
                        c["post_caption"] = social_copy.get("post_caption")
                        c["hashtags"] = social_copy.get("hashtags", [])
                        break
                with open(titles_file, "w", encoding="utf-8") as f:
                    json.dump(titles_list, f, ensure_ascii=False, indent=2)
        except Exception as fe:
            logger.debug(f"Failed to update step4_titles.json with saved social copy: {fe}")

        return {
            "clip_id": str(clip.id),
            "social_copy": social_copy,
            "success": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update social caption failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Update social caption failed: {str(e)}")