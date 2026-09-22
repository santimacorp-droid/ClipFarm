"""
API v1 package for FastAPI routes.
Centralized management of all API routes.
"""

from fastapi import APIRouter

# Create main router
api_router = APIRouter()

# Import all route modules
from .health import router as health_router
from .projects import router as projects_router
from .clips import router as clips_router
from .collections import router as collections_router
from .tasks import router as tasks_router
from .processing import router as processing_router
from .files import router as files_router
from .youtube import router as youtube_router
from .speech_recognition import router as speech_recognition_router
from .subtitle_editor import router as subtitle_editor_router
from .progress import router as progress_router
from .pipeline_control import router as pipeline_control_router
from .debug import router as debug_router
from .simple_progress import router as simple_progress_router
from .settings import router as settings_router
from .watermark import router as watermark_router
from .campaigns import router as campaigns_router

# Register all routes
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(clips_router, prefix="/clips", tags=["clips"])
api_router.include_router(collections_router, prefix="/collections", tags=["collections"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(processing_router, tags=["processing"])
api_router.include_router(files_router, tags=["files"])
api_router.include_router(youtube_router, prefix="/youtube", tags=["youtube"])
api_router.include_router(speech_recognition_router, tags=["speech-recognition"])
api_router.include_router(subtitle_editor_router, prefix="/subtitle-editor", tags=["subtitle-editor"])
api_router.include_router(progress_router, prefix="/progress", tags=["progress"])
api_router.include_router(pipeline_control_router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(debug_router, tags=["debug"])
api_router.include_router(simple_progress_router, tags=["simple-progress"])
api_router.include_router(settings_router, tags=["settings"])
api_router.include_router(watermark_router, tags=["watermarks"])
api_router.include_router(campaigns_router, tags=["campaigns"])

__all__ = ["api_router"]
