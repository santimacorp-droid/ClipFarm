"""
Campaign CRUD + pipeline trigger endpoints.
"""
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.database import get_db, SessionLocal
from backend.models.campaign import Campaign, CampaignClip
from backend.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignSchema
from backend.campaign.brief_parser import parse_brief, fast_parse_brief_heuristic
from backend.campaign.campaign_pipeline import run_campaign_pipeline

logger = logging.getLogger(__name__)

class PublishLogEntry(BaseModel):
    platform:     str   # "tiktok" | "instagram" | "youtube_shorts"
    post_url:     str
    published_at: Optional[str] = None  # ISO date, defaults to today

class SaveTemplateRequest(BaseModel):
    template_name: str

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _load_clip_data(clip: CampaignClip, clip_id: str) -> dict:
    """Safely load clip_data_json, raise HTTPException on corrupt data."""
    if not clip or not clip.clip_data_json:
        return {}
    try:
        return json.loads(clip.clip_data_json)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Clip {clip_id} malformed clip_data_json: {e}")
        raise HTTPException(
            status_code=404,
            detail="Clip data is corrupt. Please re-run the campaign pipeline."
        )


def _probe_video_file(video_path: Path) -> dict:
    """Extract duration, dimensions, and file size using ffprobe."""
    if not video_path.exists() or video_path.stat().st_size == 0:
        return {"exists": False, "duration": 0.0, "width": 0, "height": 0, "size_mb": 0.0, "filename": ""}
    
    size_mb = round(video_path.stat().st_size / (1024 * 1024), 2)
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration:format=duration",
            "-of", "json",
            str(video_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(res.stdout or "{}")
        
        duration = 0.0
        if "format" in data and "duration" in data["format"]:
            duration = float(data["format"]["duration"])
        elif "streams" in data and len(data["streams"]) > 0 and "duration" in data["streams"][0]:
            duration = float(data["streams"][0]["duration"])
            
        width = 0
        height = 0
        if "streams" in data and len(data["streams"]) > 0:
            width = int(data["streams"][0].get("width", 0))
            height = int(data["streams"][0].get("height", 0))
            
        return {
            "exists": True,
            "duration": round(duration, 2),
            "width": width,
            "height": height,
            "size_mb": size_mb,
            "filename": video_path.name
        }
    except Exception as e:
        logger.warning(f"Failed to probe video {video_path}: {e}")
        return {
            "exists": True,
            "duration": 0.0,
            "width": 0,
            "height": 0,
            "size_mb": size_mb,
            "filename": video_path.name
        }


def _download_video_with_ytdlp(url: str, dest_path: Path) -> bool:
    """Download video using yt-dlp with mp4 format."""
    ytdlp_bin = sys.executable.replace("python", "yt-dlp")
    if not Path(ytdlp_bin).exists():
        ytdlp_bin = shutil.which("yt-dlp") or "yt-dlp"
    
    try:
        logger.info(f"Downloading campaign video: {url} -> {dest_path}")
        cmd = [
            ytdlp_bin,
            "--no-playlist",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(dest_path),
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return dest_path.exists() and dest_path.stat().st_size > 1000
    except Exception as e:
        logger.warning(f"yt-dlp download failed: {e}")
        return False


@router.post("/parse-brief")
def parse_brief_endpoint(body: dict = Body(...)):
    """Parse raw brief text into structured CampaignSchema."""
    raw_brief = body.get("raw_brief", "")
    use_llm = body.get("use_llm", True)
    if not raw_brief.strip():
        raise HTTPException(status_code=400, detail="raw_brief cannot be empty")
    return parse_brief(raw_brief, use_llm=use_llm)


@router.post("")
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db)):
    """Create campaign instantly without freezing."""
    if body.schema_json:
        parsed_schema = body.schema_json
    elif body.raw_brief:
        parsed_schema = parse_brief(body.raw_brief, use_llm=False)
        parsed_schema["raw_brief"] = body.raw_brief
    else:
        parsed_schema = {
            "brand_name": body.brand_name or "Brand",
            "campaign_name": body.name or "New Campaign",
            "clip_duration": {"min_seconds": 15, "max_seconds": 60},
            "priority_moments": [],
            "caption_options": [],
            "platform_tags": {"tiktok": [], "instagram": [], "youtube_shorts": []},
            "restrictions": {
                "subtitles": "native_preferred",
                "styled_captions": False,
                "background_music": "allowed_low",
                "logo_required": True,
                "logo_position": "top_right",
                "logo_scale_percent": 0.12,
                "other_people_allowed": False,
                "external_footage_allowed": False,
                "filters_allowed": False
            },
            "compliance": {
                "min_days_live": 30,
                "min_engagement_rate": 0.002,
                "likes_must_be_visible": True,
                "tier1_2_audience_required": True,
                "ftc_compliant": True
            }
        }
    
    name = body.name or parsed_schema.get("campaign_name") or "Untitled Campaign"
    brand = body.brand_name or parsed_schema.get("brand_name") or "Brand"
    
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=name,
        brand_name=brand,
        schema_json=json.dumps(parsed_schema, ensure_ascii=False),
        status="draft"
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    
    return {
        "id":          campaign.id,
        "name":        campaign.name,
        "brand_name":  campaign.brand_name,
        "status":      campaign.status,
        "schema":      parsed_schema,
        "created_at":  campaign.created_at.isoformat() if campaign.created_at else None
    }


@router.get("")
def list_campaigns(db: Session = Depends(get_db)):
    """List all campaigns (excluding templates)."""
    campaigns = db.query(Campaign).filter(Campaign.status != "template").order_by(Campaign.created_at.desc()).all()
    res = []
    for c in campaigns:
        clips_count = len(c.clips) if c.clips else 0
        try:
            s_data = json.loads(c.schema_json)
        except Exception:
            s_data = {}
        res.append({
            "id":             c.id,
            "name":           c.name,
            "brand_name":     c.brand_name,
            "status":         c.status,
            "status_message": s_data.get("status_message", ""),
            "clips_count":    clips_count,
            "created_at":     c.created_at.isoformat() if c.created_at else None
        })
    return res


@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    """List all saved campaign templates."""
    templates = db.query(Campaign).filter_by(status="template").order_by(Campaign.created_at.desc()).all()
    return [
        {"id": t.id, "name": t.name, "brand_name": t.brand_name}
        for t in templates
    ]


@router.post("/from-template/{template_id}")
def create_from_template(template_id: str, db: Session = Depends(get_db)):
    """Create a new draft campaign pre-filled from a template's brand rules."""
    template = db.query(Campaign).filter_by(id=template_id, status="template").first()
    if not template:
        raise HTTPException(404, "Template not found")

    schema = json.loads(template.schema_json) if template.schema_json else {}
    schema['campaign_name'] = f"{template.brand_name or 'Campaign'} — New Episode"
    schema['status_message'] = ""

    new_campaign = Campaign(
        id=str(uuid.uuid4()),
        name=schema['campaign_name'],
        brand_name=template.brand_name,
        schema_json=json.dumps(schema, ensure_ascii=False),
        status="draft"
    )
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)

    return {
        "id":        new_campaign.id,
        "name":      new_campaign.name,
        "brand_name":new_campaign.brand_name,
        "status":    new_campaign.status,
        "schema":    schema
    }


# Legacy static endpoints for backwards compatibility with Kettle & Fire stitch workflow
@router.get("/kettle-fire")
async def get_kettle_fire_campaign_details():
    from ...services.campaign_service import CampaignStitchService
    return CampaignStitchService.get_campaign_info("kettle_fire_fasting")


@router.get("/sources")
async def get_campaign_sources(campaign_id: str = "kettle_fire_fasting"):
    from ...services.campaign_service import CampaignStitchService
    info = CampaignStitchService.get_campaign_info(campaign_id)
    return {
        "campaign_id": campaign_id,
        "name": info.get("name"),
        "approved_sources": info.get("approved_sources", [])
    }


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Get campaign details + clips."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    clips = db.query(CampaignClip).filter_by(campaign_id=campaign_id).all()
    
    try:
        parsed_schema = json.loads(campaign.schema_json)
    except Exception:
        parsed_schema = {}

    parsed_clips = []
    for c in clips:
        try:
            data = json.loads(c.clip_data_json) if c.clip_data_json else {}
        except Exception:
            data = {}
        data['id'] = c.id
        data['campaign_id'] = c.campaign_id
        data['status'] = c.status
        data['moment_name'] = data.get('moment_name') or c.moment_name
        if 'start_sec' in data and data['start_sec'] is not None:
            data['start_sec'] = float(data['start_sec'])
        if 'end_sec' in data and data['end_sec'] is not None:
            data['end_sec'] = float(data['end_sec'])
        parsed_clips.append(data)
    
    return {
        "id":             campaign.id,
        "name":           campaign.name,
        "brand_name":     campaign.brand_name,
        "status":         campaign.status,
        "status_message": parsed_schema.get("status_message", ""),
        "schema":         parsed_schema,
        "clips":          parsed_clips,
        "created_at":     campaign.created_at.isoformat() if campaign.created_at else None
    }


@router.put("/{campaign_id}")
def update_campaign(campaign_id: str, body: CampaignUpdate, db: Session = Depends(get_db)):
    """Update parsed schema (user corrections)."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    campaign.schema_json = json.dumps(body.schema_json, ensure_ascii=False)
    if "campaign_name" in body.schema_json:
        campaign.name = body.schema_json["campaign_name"]
    if "brand_name" in body.schema_json:
        campaign.brand_name = body.schema_json["brand_name"]
    campaign.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "updated"}


@router.post("/{campaign_id}/upload-video")
async def upload_campaign_video(
    campaign_id: str,
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Directly upload source video file for campaign."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    ext = Path(video_file.filename).suffix.lower()
    if ext not in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {ext}")
        
    camp_dir = Path("data/campaigns") / campaign_id
    camp_dir.mkdir(parents=True, exist_ok=True)
    sources_dir = camp_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    
    file_in_sources = sources_dir / video_file.filename
    with open(file_in_sources, "wb") as f:
        content = await video_file.read()
        f.write(content)
        
    dest_path = camp_dir / "source.mp4"
    shutil.copyfile(file_in_sources, dest_path)
        
    probe_info = _probe_video_file(dest_path)
    
    try:
        s_data = json.loads(campaign.schema_json)
    except Exception:
        s_data = {}
        
    s_data["source_video_url"] = f"file://{video_file.filename}"
    s_data["source_filename"] = video_file.filename
    s_data["source_duration"] = probe_info["duration"]
    s_data["status_message"] = "Video ready for clipping"
    campaign.schema_json = json.dumps(s_data, ensure_ascii=False)
    campaign.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "uploaded",
        **probe_info,
        "filename": video_file.filename
    }


@router.post("/{campaign_id}/import-url")
def import_campaign_video_url(
    campaign_id: str,
    body: dict = Body(...),
    db: Session = Depends(get_db)
):
    """Download video from YouTube/Web URL into campaign directory."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
        
    camp_dir = Path("data/campaigns") / campaign_id
    camp_dir.mkdir(parents=True, exist_ok=True)
    dest_path = camp_dir / "source.mp4"
    
    success = _download_video_with_ytdlp(url, dest_path)
    if not success:
        from backend.campaign.campaign_pipeline import _acquire_source_video
        acquired = _acquire_source_video(url, camp_dir)
        success = acquired is not None and acquired.exists()
        
    if not success or not dest_path.exists() or dest_path.stat().st_size < 1000:
        raise HTTPException(
            status_code=400,
            detail="Failed to download video from URL. Please upload the video file directly."
        )
        
    probe_info = _probe_video_file(dest_path)
    
    try:
        s_data = json.loads(campaign.schema_json)
    except Exception:
        s_data = {}
        
    s_data["source_video_url"] = url
    s_data["source_filename"] = Path(url).name or "downloaded_video.mp4"
    s_data["source_duration"] = probe_info["duration"]
    s_data["status_message"] = "Video downloaded and ready"
    campaign.schema_json = json.dumps(s_data, ensure_ascii=False)
    campaign.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "status": "imported",
        "url": url,
        **probe_info
    }


@router.post("/{campaign_id}/upload-logo")
async def upload_campaign_logo(
    campaign_id: str,
    logo_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload brand logo watermark PNG directly."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    assets_dir = Path("data/campaigns") / campaign_id / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    logo_path = assets_dir / "logo.png"
    
    with open(logo_path, "wb") as f:
        content = await logo_file.read()
        f.write(content)
        
    try:
        s_data = json.loads(campaign.schema_json)
    except Exception:
        s_data = {}
    s_data["logo_url"] = str(logo_path)
    campaign.schema_json = json.dumps(s_data, ensure_ascii=False)
    campaign.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "uploaded", "logo_url": str(logo_path)}


@router.delete("/{campaign_id}/logo")
def delete_campaign_logo(campaign_id: str, db: Session = Depends(get_db)):
    """Remove watermark logo and mark logo as not required."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    assets_dir = Path("data/campaigns") / campaign_id / "assets"
    logo_path = assets_dir / "logo.png"
    if logo_path.exists():
        try:
            logo_path.unlink()
        except Exception:
            pass
            
    try:
        s_data = json.loads(campaign.schema_json)
    except Exception:
        s_data = {}
        
    s_data["logo_url"] = None
    if "restrictions" in s_data:
        s_data["restrictions"]["logo_required"] = False
    campaign.schema_json = json.dumps(s_data, ensure_ascii=False)
    campaign.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "logo_removed"}


@router.api_route("/{campaign_id}/logo", methods=["GET", "HEAD"])
def get_campaign_logo(campaign_id: str, db: Session = Depends(get_db)):
    """Get the campaign watermark logo image if present."""
    logo_path = Path("data/campaigns") / campaign_id / "assets" / "logo.png"
    if not logo_path.exists() or logo_path.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="No logo uploaded")
    return FileResponse(logo_path, media_type="image/png")


@router.get("/{campaign_id}/sources")
def list_campaign_sources(campaign_id: str, db: Session = Depends(get_db)):
    """List all available source video files for this campaign."""
    camp_dir = Path("data/campaigns") / campaign_id
    sources_dir = camp_dir / "sources"
    
    files = []
    active_size = (camp_dir / "source.mp4").stat().st_size if (camp_dir / "source.mp4").exists() else -1
    
    if sources_dir.exists():
        for p in sorted(sources_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
                info = _probe_video_file(p)
                files.append({
                    "filename": p.name,
                    "is_active": p.stat().st_size == active_size,
                    **info
                })
    
    if not files and (camp_dir / "source.mp4").exists():
        info = _probe_video_file(camp_dir / "source.mp4")
        files.append({
            "filename": "source.mp4",
            "is_active": True,
            **info
        })
        
    return files


@router.post("/{campaign_id}/select-source")
def select_campaign_source(campaign_id: str, body: dict = Body(...), db: Session = Depends(get_db)):
    """Set an uploaded file as the active source.mp4 for clipping."""
    filename = body.get("filename")
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
        
    camp_dir = Path("data/campaigns") / campaign_id
    target = camp_dir / "sources" / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="Source file not found")
        
    dest_path = camp_dir / "source.mp4"
    shutil.copyfile(target, dest_path)
    probe = _probe_video_file(dest_path)
    
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if campaign:
        try:
            s_data = json.loads(campaign.schema_json)
        except Exception:
            s_data = {}
        s_data["source_filename"] = filename
        s_data["source_duration"] = probe["duration"]
        campaign.schema_json = json.dumps(s_data, ensure_ascii=False)
        campaign.updated_at = datetime.utcnow()
        db.commit()
        
    return {"status": "active_source_updated", **probe}


@router.get("/{campaign_id}/source-info")
def get_campaign_source_info(campaign_id: str, db: Session = Depends(get_db)):
    """Check if source video exists and return metadata."""
    camp_dir = Path("data/campaigns") / campaign_id
    dest_path = camp_dir / "source.mp4"
    return _probe_video_file(dest_path)


@router.api_route("/{campaign_id}/source-video", methods=["GET", "HEAD"])
def get_campaign_source_video(campaign_id: str, db: Session = Depends(get_db)):
    """Stream source video for in-browser preview."""
    camp_dir = Path("data/campaigns") / campaign_id
    dest_path = camp_dir / "source.mp4"
    if not dest_path.exists() or dest_path.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="Source video not found or empty")
    return FileResponse(
        path=dest_path,
        media_type="video/mp4",
        content_disposition_type="inline",
        filename="source.mp4",
        headers={"Accept-Ranges": "bytes"}
    )


@router.post("/{campaign_id}/run")
def run_campaign(campaign_id: str, force: bool = False, db: Session = Depends(get_db)):
    """Trigger campaign pipeline in background thread."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if not force and campaign.status in ("downloading", "transcribing", "finding_moments", "cutting", "editing", "active"):
        # If campaign has been in running state for > 3 minutes without update, assume previous thread died
        stale_threshold = datetime.utcnow() - timedelta(minutes=3)
        if campaign.updated_at and campaign.updated_at > stale_threshold:
            raise HTTPException(status_code=409, detail="Campaign is already running")
        logger.warning(f"Campaign {campaign_id} was stuck in status '{campaign.status}'. Overriding.")
    
    try:
        schema_dict = json.loads(campaign.schema_json)
    except Exception:
        schema_dict = {}
    
    # Check if video is present or URL is available
    camp_video = Path("data/campaigns") / campaign_id / "source.mp4"
    has_video = camp_video.exists() and camp_video.stat().st_size > 1000
    has_url = bool(schema_dict.get("source_video_url"))
    
    if not has_video and not has_url:
        raise HTTPException(
            status_code=400,
            detail="Source video missing. Please upload a video file or provide a video URL before running."
        )
    
    # Run in background thread
    thread = threading.Thread(
        target=run_campaign_pipeline,
        args=(campaign_id, schema_dict),
        daemon=True
    )
    thread.start()
    
    return {"status": "started", "campaign_id": campaign_id}


@router.post("/{campaign_id}/reset")
def reset_campaign_status(campaign_id: str, db: Session = Depends(get_db)):
    """Reset a stuck campaign status back to draft."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = "draft"
    try:
        s_data = json.loads(campaign.schema_json) if campaign.schema_json else {}
    except Exception:
        s_data = {}
    s_data["status_message"] = "Pipeline reset by user. Ready to cut clips."
    campaign.schema_json = json.dumps(s_data, ensure_ascii=False)
    campaign.updated_at = datetime.utcnow()
    db.commit()
    logger.info(f"Campaign {campaign_id} status reset to draft")
    return {"status": "reset", "campaign_id": campaign_id}


@router.api_route(
    "/{campaign_id}/clips/{clip_id}/video",
    methods=["GET", "HEAD"]
)
def get_campaign_clip_video(
    campaign_id: str,
    clip_id: str,
    platform: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Stream campaign clip video with byte-range support."""
    # Step 1: Fetch clip record
    clip = db.query(CampaignClip).filter_by(id=clip_id, campaign_id=campaign_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Step 2: Parse clip_data_json safely
    try:
        data = json.loads(clip.clip_data_json) if clip.clip_data_json else {}
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Clip {clip_id} has malformed clip_data_json: {e}")
        raise HTTPException(status_code=404, detail="Clip data is corrupt — please re-run the campaign pipeline")

    # Step 3: Resolve video path
    video_path = None
    if platform:
        plat_key = str(platform).lower().replace("-", "_").strip()
        cta_platforms = data.get("cta_platforms") or data.get("platform_videos") or {}
        if isinstance(cta_platforms, dict) and plat_key in cta_platforms:
            candidate = cta_platforms[plat_key]
            if candidate and os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                video_path = candidate

    if not video_path:
        # Precedence: CTA overlay version -> video_file -> captioned -> logo -> vertical
        candidates = [
            data.get("cta_video_file"),
            data.get("video_file"),
            data.get("captioned_video_file"),
            data.get("logo_video_file"),
            data.get("vertical_video_file"),
        ]
        for cand in candidates:
            if cand and os.path.exists(cand) and os.path.getsize(cand) > 0:
                video_path = cand
                break

    # Step 4: Validate path exists
    if not video_path:
        raise HTTPException(
            status_code=404,
            detail="No video path recorded for this clip. Re-run the campaign pipeline."
        )
    if not os.path.exists(video_path):
        raise HTTPException(
            status_code=404,
            detail="Video file not found on disk. The file may have been moved or deleted. Re-run the pipeline."
        )
    if os.path.getsize(video_path) == 0:
        raise HTTPException(
            status_code=404,
            detail="Video file exists but is empty (0 bytes). Re-run the campaign pipeline."
        )

    # Step 5: Serve with correct headers
    plat_suffix = f"_{platform.lower()}" if platform else ""
    safe_name = re.sub(r'[^\w\-.]', '_', f"{clip.moment_name or clip_id}{plat_suffix}.mp4")
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        content_disposition_type="inline",
        filename=safe_name,
        headers={"Accept-Ranges": "bytes"}
    )


@router.api_route("/{campaign_id}/clips/{clip_id}/srt", methods=["GET", "HEAD"])
def download_clip_srt(campaign_id: str, clip_id: str, db: Session = Depends(get_db)):
    """Download the SRT subtitle file for a clip."""
    clip = db.query(CampaignClip).filter_by(id=clip_id, campaign_id=campaign_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    try:
        data = json.loads(clip.clip_data_json) if clip.clip_data_json else {}
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Clip {clip_id} malformed clip_data_json: {e}")
        raise HTTPException(status_code=404, detail="Clip data is corrupt")
    
    srt_path = data.get("srt_file")
    
    if not srt_path or not os.path.exists(srt_path) or os.path.getsize(srt_path) == 0:
        raise HTTPException(
            status_code=404,
            detail="SRT file not found. Re-run pipeline with 'SRT File' caption mode selected."
        )
    
    safe_name = re.sub(r'[^\w\-.]', '_', f"{clip.moment_name or clip_id}.srt")
    return FileResponse(path=srt_path, media_type="text/plain", filename=safe_name)


@router.get("/{campaign_id}/export")
def export_campaign_zip(campaign_id: str, db: Session = Depends(get_db)):
    """Download all campaign clips + post guides as a ZIP file."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    clips    = db.query(CampaignClip).filter_by(campaign_id=campaign_id).all()
    schema   = json.loads(campaign.schema_json) if campaign.schema_json else {}

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add original brief
        raw_brief = schema.get("raw_brief", "")
        if raw_brief:
            zf.writestr("campaign_brief.txt", raw_brief)

        for clip_record in clips:
            try:
                data = json.loads(clip_record.clip_data_json) if clip_record.clip_data_json else {}
            except Exception:
                continue

            safe_name = re.sub(r'[^\w\s-]', '', data.get('moment_name', f'clip_{clip_record.id[:8]}')).strip().replace(' ', '_')

            # Write platform-specific CTA videos if present
            cta_platforms = data.get('cta_platforms') or data.get('platform_videos') or {}
            if isinstance(cta_platforms, dict):
                for plat_name, p_path in cta_platforms.items():
                    if p_path and os.path.exists(p_path) and os.path.getsize(p_path) > 0:
                        zf.write(p_path, f"clips/{safe_name}/{plat_name}.mp4")

            # Write master / primary video file
            cta_path       = data.get('cta_video_file')
            raw_path       = data.get('video_file')
            captioned_path = data.get('captioned_video_file')
            logo_path      = data.get('logo_video_file')
            vertical_path  = data.get('vertical_video_file')

            video_path = None
            for p in [cta_path, raw_path, captioned_path, logo_path, vertical_path]:
                if p and os.path.exists(p) and os.path.getsize(p) > 0:
                    video_path = p
                    break

            if video_path and os.path.exists(video_path):
                zf.write(video_path, f"clips/{safe_name}/clip.mp4")

            # Include SRT file if available
            srt_path = data.get('srt_file')
            if srt_path and os.path.exists(srt_path):
                zf.write(srt_path, f"clips/{safe_name}/captions.srt")

            # Post guide text
            guide_lines = [f"=== {data.get('moment_name', 'Clip')} ===", ""]
            for platform, guide in (data.get('platform_post_guide') or {}).items():
                guide_lines.append(f"--- {platform.upper().replace('_', ' ')} ---")
                if guide.get('title'):
                    guide_lines.append(f"Title: {guide['title']}")
                guide_lines.append(f"Caption:\n{guide.get('caption', '')}")
                guide_lines.append("")
            zf.writestr(f"clips/{safe_name}/post_guide.txt", "\n".join(guide_lines))

    zip_buffer.seek(0)
    safe_campaign_name = re.sub(r'[^\w\s-]', '', campaign.name[:40]).strip().replace(' ', '_')
    filename = f"{safe_campaign_name}_clips.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


@router.post("/{campaign_id}/save-template")
def save_as_template(campaign_id: str, body: SaveTemplateRequest, db: Session = Depends(get_db)):
    """Save campaign brand rules as a reusable template (new campaign with status='template')."""
    source = db.query(Campaign).filter_by(id=campaign_id).first()
    if not source:
        raise HTTPException(404, "Campaign not found")

    source_schema = json.loads(source.schema_json) if source.schema_json else {}

    # Strip episode-specific fields
    template_schema = {k: v for k, v in source_schema.items() if k not in (
        'source_video_url', 'priority_moments', 'raw_brief', 'status_message'
    )}
    template_schema['priority_moments'] = []   # empty — user fills per episode
    template_schema['source_video_url'] = None
    template_schema['campaign_name']    = body.template_name
    template_schema['raw_brief']        = f"Template derived from: {source.name}"

    template = Campaign(
        id=str(uuid.uuid4()),
        name=body.template_name,
        brand_name=source.brand_name or source_schema.get("brand_name"),
        schema_json=json.dumps(template_schema, ensure_ascii=False),
        status="template"
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return {"id": template.id, "name": template.name, "status": "template"}


@router.post("/{campaign_id}/clips/{clip_id}/publish-log")
def log_clip_publish(
    campaign_id: str,
    clip_id:     str,
    body:        PublishLogEntry,
    db:          Session = Depends(get_db)
):
    """Log that a clip was posted to a platform."""
    clip = db.query(CampaignClip).filter_by(id=clip_id, campaign_id=campaign_id).first()
    if not clip:
        raise HTTPException(404, "Clip not found")
    
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    schema_data = json.loads(campaign.schema_json) if campaign and campaign.schema_json else {}
    min_days = schema_data.get("compliance", {}).get("min_days_live", 30)
    
    published_date = body.published_at or datetime.utcnow().strftime("%Y-%m-%d")
    try:
        expires_date = (
            datetime.strptime(published_date, "%Y-%m-%d") + timedelta(days=min_days)
        ).strftime("%Y-%m-%d")
    except Exception:
        expires_date = published_date
    
    try:
        data = json.loads(clip.clip_data_json) if clip.clip_data_json else {}
    except Exception:
        data = {}
    
    publish_log = data.get("publish_log", [])
    
    # Update existing entry for this platform, or add new
    existing = next((e for e in publish_log if e.get("platform") == body.platform), None)
    entry = {
        "platform":     body.platform,
        "post_url":     body.post_url,
        "published_at": published_date,
        "expires_at":   expires_date
    }
    if existing:
        publish_log[publish_log.index(existing)] = entry
    else:
        publish_log.append(entry)
    
    data["publish_log"] = publish_log
    clip.clip_data_json = json.dumps(data, ensure_ascii=False)
    db.commit()
    
    return {"status": "logged", "entry": entry}


@router.delete("/{campaign_id}/clips/{clip_id}/publish-log/{platform}")
def remove_publish_log(campaign_id: str, clip_id: str, platform: str, db: Session = Depends(get_db)):
    """Remove a publish log entry (e.g. if post was taken down early)."""
    clip = db.query(CampaignClip).filter_by(id=clip_id, campaign_id=campaign_id).first()
    if not clip:
        raise HTTPException(404, "Clip not found")
    try:
        data = json.loads(clip.clip_data_json) if clip.clip_data_json else {}
    except Exception:
        data = {}
    data["publish_log"] = [e for e in data.get("publish_log", []) if e.get("platform") != platform]
    clip.clip_data_json = json.dumps(data, ensure_ascii=False)
    db.commit()
    return {"status": "removed"}


class ClipCopyUpdate(BaseModel):
    hook_text: Optional[str] = None
    platform_post_guide: Optional[dict] = None


@router.post("/{campaign_id}/clips/{clip_id}/regenerate-copy")
def regenerate_clip_copy(campaign_id: str, clip_id: str, db: Session = Depends(get_db)):
    """Regenerate on-screen hook and search-optimized platform copy for a specific clip."""
    clip = db.query(CampaignClip).filter_by(id=clip_id, campaign_id=campaign_id).first()
    if not clip:
        raise HTTPException(404, "Clip not found")
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    try:
        schema = json.loads(campaign.schema_json) if campaign.schema_json else {}
        data = json.loads(clip.clip_data_json) if clip.clip_data_json else {}
    except Exception:
        raise HTTPException(500, "Error decoding campaign or clip metadata")

    from backend.campaign.copy_generator import generate_clip_copy_and_hook
    
    transcript = data.get("matched_text", "")
    srt_file = data.get("srt_file")
    if srt_file and Path(srt_file).exists():
        try:
            with open(srt_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                clean = re.sub(r'\d+\n\d{2}:\d{2}:\d{2}[,\.]\d+ --> \d{2}:\d{2}:\d{2}[,\.]\d+\n', '', content)
                transcript = re.sub(r'<[^>]+>', '', clean).strip()
        except Exception:
            pass

    brand_name = campaign.brand_name or schema.get("brand_name", "Brand")
    platform_tags = schema.get("platform_tags", {})
    caption_options = schema.get("caption_options", [])

    copy_res = generate_clip_copy_and_hook(
        moment_name=clip.moment_name,
        transcript_text=transcript,
        brand_name=brand_name,
        description=clip.moment_name,
        platform_tags=platform_tags,
        caption_options=caption_options
    )

    hook_text = copy_res.get("hook_text", "")
    post_guide = {
        "tiktok": copy_res.get("tiktok", {}),
        "instagram": copy_res.get("instagram", {}),
        "youtube_shorts": copy_res.get("youtube_shorts", {}),
        "facebook": copy_res.get("facebook", {})
    }

    data["hook_text"] = hook_text
    data["platform_post_guide"] = post_guide
    clip.clip_data_json = json.dumps(data, ensure_ascii=False)
    db.commit()

    return {
        "status": "regenerated",
        "hook_text": hook_text,
        "platform_post_guide": post_guide
    }


@router.put("/{campaign_id}/clips/{clip_id}/copy")
def update_clip_copy(campaign_id: str, clip_id: str, body: ClipCopyUpdate, db: Session = Depends(get_db)):
    """Update on-screen hook or platform copy for a specific clip."""
    clip = db.query(CampaignClip).filter_by(id=clip_id, campaign_id=campaign_id).first()
    if not clip:
        raise HTTPException(404, "Clip not found")

    try:
        data = json.loads(clip.clip_data_json) if clip.clip_data_json else {}
    except Exception:
        data = {}

    if body.hook_text is not None:
        data["hook_text"] = body.hook_text.strip().upper()
    if body.platform_post_guide is not None:
        data["platform_post_guide"] = body.platform_post_guide

    clip.clip_data_json = json.dumps(data, ensure_ascii=False)
    db.commit()

    return {
        "status": "updated",
        "hook_text": data.get("hook_text"),
        "platform_post_guide": data.get("platform_post_guide")
    }


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """Archive/delete campaign."""
    campaign = db.query(Campaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    camp_dir = Path("data/campaigns") / campaign_id
    if camp_dir.exists():
        shutil.rmtree(camp_dir, ignore_errors=True)
        
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}
