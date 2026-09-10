"""
Affiliate Marketing API Endpoints
Provides endpoints for creating affiliate videos with Filipino captions and Facebook Follow CTA.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.affiliate.affiliate_processor import AffiliateVideoProcessor
from backend.utils.caption_styles import CAPTION_STYLES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/affiliate", tags=["affiliate"])


class ProcessVideoRequest(BaseModel):
    video_path: str
    output_dir: Optional[str] = None
    transcript_path: Optional[str] = None
    transcript_text: Optional[str] = None
    fb_handle: Optional[str] = ""
    caption_style: Optional[str] = "hormozi_yellow"
    cta_style: Optional[str] = "pill"
    cta_position: Optional[str] = "lower_middle"
    watermark: Optional[bool] = True
    language: Optional[str] = "tl"
    engine: Optional[str] = "gemini"


@router.get("/styles")
async def get_caption_styles() -> Dict[str, Any]:
    """Return available caption styling presets and CTA options."""
    styles = []
    for key, val in CAPTION_STYLES.items():
        styles.append({
            "key": key,
            "name": val.get("name", key),
            "font_size": val.get("font_size", 72),
            "uppercase": val.get("uppercase", True)
        })
    return {
        "styles": styles,
        "default_style": "hormozi_yellow",
        "default_language": "tl",
        "supported_languages": [
            {"code": "tl", "name": "Tagalog / Filipino"},
            {"code": "en", "name": "English"}
        ],
        "cta": {
            "platform": "facebook",
            "action": "Follow",
            "supported_styles": ["pill", "card"],
            "supported_positions": ["lower_middle", "lower_center", "lower_third", "bottom_center"]
        }
    }


@router.get("/video")
async def get_affiliate_video(filename: str):
    """Serve processed video file for playback and download."""
    p = Path("data/output/affiliate").resolve() / filename
    if not p.exists() or not p.is_file():
        p = Path(filename).resolve()
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(path=str(p), media_type="video/mp4", filename=p.name)


@router.get("/recent")
async def list_recent_affiliate_videos() -> List[Dict[str, Any]]:
    """List already processed affiliate videos in data/output/affiliate."""
    out_dir = Path("data/output/affiliate").resolve()
    if not out_dir.exists():
        return []
    videos = []
    for f in sorted(out_dir.glob("*_filipino_fb.mp4"), key=os.path.getmtime, reverse=True):
        srt_file = f.parent / f"{f.stem}.srt"
        stat = f.stat()
        videos.append({
            "filename": f.name,
            "path": str(f),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": stat.st_mtime,
            "has_srt": srt_file.exists(),
            "video_url": f"/api/v1/affiliate/video?filename={f.name}"
        })
    return videos


@router.get("/candidates")
async def list_candidate_videos() -> List[Dict[str, Any]]:
    """Find available affiliate candidate videos from Downloads and data folders."""
    candidates = []
    search_dirs = [
        Path.home() / "Downloads",
        Path("data").resolve(),
    ]
    seen_paths = set()
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for ext in ["*.mp4", "*.mov"]:
            for f in sdir.glob(ext):
                if f.name.endswith("_filipino_fb.mp4"):
                    continue
                if str(f) in seen_paths:
                    continue
                seen_paths.add(str(f))
                try:
                    candidates.append({
                        "filename": f.name,
                        "path": str(f),
                        "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                        "mtime": f.stat().st_mtime
                    })
                except Exception:
                    pass
    candidates.sort(key=lambda x: x["mtime"], reverse=True)
    return candidates[:20]


@router.post("/process-path")
async def process_video_by_path(req: ProcessVideoRequest) -> Dict[str, Any]:
    """Process an existing local video path."""
    p = Path(req.video_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Video path not found: {req.video_path}")

    output_dir = Path(req.output_dir or "data/output/affiliate").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    out_video = output_dir / f"{p.stem}_filipino_fb.mp4"

    try:
        processor = AffiliateVideoProcessor(
            whisper_model="small",
            default_caption_style=req.caption_style or "hormozi_yellow",
            default_engine=req.engine or "auto"
        )
        transcript_src = req.transcript_path or req.transcript_text or None
        result = processor.process_affiliate_video(
            input_video_path=p,
            output_video_path=out_video,
            transcript_source=transcript_src,
            fb_handle=req.fb_handle or "",
            caption_style=req.caption_style or "hormozi_yellow",
            cta_style=req.cta_style or "pill",
            cta_position=req.cta_position or "lower_middle",
            language=req.language or "tl",
            engine=req.engine or "auto",
            watermark=req.watermark if req.watermark is not None else True
        )
        result["video_url"] = f"/api/v1/affiliate/video?filename={out_video.name}"
        return result
    except Exception as e:
        logger.error(f"Failed to process affiliate video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-upload")
async def process_video_upload(
    video_file: UploadFile = File(...),
    transcript_file: Optional[UploadFile] = File(None),
    transcript_text: Optional[str] = Form(None),
    fb_handle: str = Form(""),
    caption_style: str = Form("hormozi_yellow"),
    cta_style: str = Form("pill"),
    cta_position: str = Form("lower_middle"),
    watermark: bool = Form(True),
    language: str = Form("tl"),
    engine: str = Form("gemini")
) -> Dict[str, Any]:
    """Upload and process a video file directly with optional custom transcript."""
    uploads_dir = Path("data/uploads/affiliate").resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    filename = video_file.filename or "video.mp4"
    temp_input_path = uploads_dir / filename
    
    try:
        with open(temp_input_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)

        transcript_src = None
        if transcript_file and transcript_file.filename:
            transcript_path = uploads_dir / f"transcript_{transcript_file.filename}"
            with open(transcript_path, "wb") as buffer:
                shutil.copyfileobj(transcript_file.file, buffer)
            transcript_src = transcript_path
        elif transcript_text and transcript_text.strip():
            transcript_src = transcript_text.strip()
            
        output_dir = Path("data/output/affiliate").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        out_video = output_dir / f"{temp_input_path.stem}_filipino_fb.mp4"

        processor = AffiliateVideoProcessor(
            whisper_model="small",
            default_caption_style=caption_style,
            default_engine=engine
        )
        result = processor.process_affiliate_video(
            input_video_path=temp_input_path,
            output_video_path=out_video,
            transcript_source=transcript_src,
            fb_handle=fb_handle,
            caption_style=caption_style,
            cta_style=cta_style,
            cta_position=cta_position,
            watermark=watermark,
            language=language,
            engine=engine
        )
        result["video_url"] = f"/api/v1/affiliate/video?filename={out_video.name}"
        return result
    except Exception as e:
        logger.error(f"Failed to process uploaded affiliate video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
