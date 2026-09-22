"""
Health checkAPIRoute
"""

from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@router.get("/video-categories")
async def get_video_categories() -> Dict[str, Any]:
    """Get video category configurations."""
    from ...core.shared_config import VIDEO_CATEGORIES_CONFIG, VideoCategory
    categories_list = []
    for cat, meta in VIDEO_CATEGORIES_CONFIG.items():
        if cat == VideoCategory.DEFAULT:
            continue
        categories_list.append({
            "value": cat.value,
            "name": meta.get("name", cat.value),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", "video"),
            "color": meta.get("color", "#1890ff")
        })
    return {
        "categories": categories_list,
        "default_category": "podcast"
    }