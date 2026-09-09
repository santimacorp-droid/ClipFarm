"""
API v1 package for FastAPI routes.
Centralized management of allAPIRoute
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
# from .websocket import router as websocket_router  # DisabledWebSocketSystem
from .files import router as files_router
from .bilibili import router as bilibili_router
from .youtube import router as youtube_router
from .speech_recognition import router as speech_recognition_router
from .subtitle_editor import router as subtitle_editor_router
from .upload import router as upload_router
from .progress import router as progress_router
from .pipeline_control import router as pipeline_control_router
from .debug import router as debug_router
from .simple_progress import router as simple_progress_router
# from .environment import router as environment_router  # File does not exist, temporarily commented out
from .settings import router as settings_router
from .watermark import router as watermark_router
from ..upload_queue import router as upload_queue_router
from ..account_health import router as account_health_router
from .campaigns import router as campaigns_router
from .affiliate import router as affiliate_router

# Register all routes
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(clips_router, prefix="/clips", tags=["clips"])
api_router.include_router(collections_router, prefix="/collections", tags=["collections"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(processing_router, tags=["processing"])
# api_router.include_router(websocket_router, tags=["websocket"])  # DisabledWebSocketSystem
api_router.include_router(files_router, tags=["files"])
api_router.include_router(bilibili_router, prefix="/bilibili", tags=["bilibili"])
api_router.include_router(youtube_router, prefix="/youtube", tags=["youtube"])
api_router.include_router(speech_recognition_router, tags=["speech-recognition"])
api_router.include_router(subtitle_editor_router, prefix="/subtitle-editor", tags=["subtitle-editor"])
api_router.include_router(upload_router, tags=["upload"])
api_router.include_router(progress_router, prefix="/progress", tags=["progress"])
api_router.include_router(pipeline_control_router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(debug_router, tags=["debug"])
api_router.include_router(simple_progress_router, tags=["simple-progress"])
# api_router.include_router(environment_router, tags=["environment"])  # File does not exist, temporarily commented out
api_router.include_router(settings_router, tags=["settings"])
api_router.include_router(watermark_router, tags=["watermarks"])
api_router.include_router(upload_queue_router, tags=["upload-queue"])
api_router.include_router(account_health_router, tags=["account-health"])
api_router.include_router(campaigns_router, tags=["campaigns"])
api_router.include_router(affiliate_router, tags=["affiliate"])

__all__ = ["api_router"]
