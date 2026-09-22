"""
Watermark API Endpoints
Provides management of watermark / campaign presets and logo assets.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.services.watermark_service import watermark_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/watermarks", tags=["watermarks"])


class WatermarkPresetUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    scale_percent: Optional[int] = None
    opacity: Optional[float] = None
    margin: Optional[int] = None
    is_default: Optional[bool] = None


@router.get("/presets")
async def list_watermark_presets() -> List[Dict[str, Any]]:
    """List all saved watermark presets."""
    return watermark_service.get_all_presets()


@router.post("/presets")
async def create_watermark_preset(
    name: str = Form(...),
    logo_file: UploadFile = File(...),
    position: str = Form("bottom_right"),
    scale_percent: int = Form(15),
    opacity: float = Form(0.85),
    margin: int = Form(24),
    is_default: bool = Form(False)
) -> Dict[str, Any]:
    """Upload a logo image and create a new reusable watermark preset."""
    try:
        # Validate image extension
        ext = Path(logo_file.filename or "").suffix.lower()
        if ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
            raise HTTPException(status_code=400, detail="Invalid logo file format (use PNG, JPG, WEBP, or SVG)")

        file_bytes = await logo_file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty logo file uploaded")

        saved_filename = watermark_service.save_logo_file(file_bytes, logo_file.filename or "logo.png")
        preset = watermark_service.create_preset(
            name=name,
            logo_filename=saved_filename,
            position=position,
            scale_percent=scale_percent,
            opacity=opacity,
            margin=margin,
            is_default=is_default
        )
        return preset
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create watermark preset: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create watermark preset: {str(e)}")


@router.put("/presets/{preset_id}")
async def update_watermark_preset(preset_id: str, updates: WatermarkPresetUpdate) -> Dict[str, Any]:
    """Update an existing watermark preset."""
    updated = watermark_service.update_preset(preset_id, updates.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Watermark preset not found")
    return updated


@router.delete("/presets/{preset_id}")
async def delete_watermark_preset(preset_id: str) -> Dict[str, Any]:
    """Delete a watermark preset."""
    success = watermark_service.delete_preset(preset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Watermark preset not found")
    return {"success": True, "message": "Watermark preset deleted"}


@router.get("/logos/{filename}")
async def get_watermark_logo(filename: str):
    """Serve a logo image file for frontend preview."""
    logo_path = watermark_service.get_logo_path(filename)
    if not logo_path or not logo_path.exists():
        raise HTTPException(status_code=404, detail="Logo file not found")
    
    # Determine content type
    ext = logo_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml"
    }
    media_type = media_types.get(ext, "image/png")
    return FileResponse(path=str(logo_path), media_type=media_type)
