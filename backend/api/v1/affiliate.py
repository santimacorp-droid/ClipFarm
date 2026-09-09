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
from pydantic import BaseModel

from backend.affiliate.affiliate_processor import AffiliateVideoProcessor
from backend.utils.caption_styles import CAPTION_STYLES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/affiliate", tags=["affiliate"])


class ProcessVideoRequest(BaseModel):
    video_path: str
    output_dir: Optional[str] = None
    fb_handle: Optional[str] = ""
    caption_style: Optional[str] = "hormozi_yellow"
    cta_style: Optional[str] = "pill"
    cta_position: Optional[str] = "lower_center"
    language: Optional[str] = "tl"


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
            "supported_positions": ["lower_center", "lower_third", "bottom_center"]
        }
    }


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
            whisper_model="base",
            default_caption_style=req.caption_style or "hormozi_yellow"
        )
        result = processor.process_affiliate_video(
            input_video_path=p,
            output_video_path=out_video,
            fb_handle=req.fb_handle or "",
            caption_style=req.caption_style or "hormozi_yellow",
            cta_style=req.cta_style or "pill",
            cta_position=req.cta_position or "lower_center",
            language=req.language or "tl"
        )
        return result
    except Exception as e:
        logger.error(f"Failed to process affiliate video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-upload")
async def process_video_upload(
    video_file: UploadFile = File(...),
    fb_handle: str = Form(""),
    caption_style: str = Form("hormozi_yellow"),
    cta_style: str = Form("pill"),
    cta_position: str = Form("lower_center"),
    language: str = Form("tl")
) -> Dict[str, Any]:
    """Upload and process a video file directly."""
    uploads_dir = Path("data/uploads/affiliate").resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    filename = video_file.filename or "video.mp4"
    temp_input_path = uploads_dir / filename
    
    try:
        with open(temp_input_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)
            
        output_dir = Path("data/output/affiliate").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        out_video = output_dir / f"{temp_input_path.stem}_filipino_fb.mp4"

        processor = AffiliateVideoProcessor(
            whisper_model="base",
            default_caption_style=caption_style
        )
        result = processor.process_affiliate_video(
            input_video_path=temp_input_path,
            output_video_path=out_video,
            fb_handle=fb_handle,
            caption_style=caption_style,
            cta_style=cta_style,
            cta_position=cta_position,
            language=language
        )
        return result
    except Exception as e:
        logger.error(f"Failed to process uploaded affiliate video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
