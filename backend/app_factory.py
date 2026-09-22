"""
Single backend application factory function web and desktop two modes
"""
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.v1 import api_router
from backend.api.v1.health import router as health_router
from backend.core.database import engine
from backend.models.base import Base
from backend.core.config import get_logging_config, get_api_key
from backend.core.error_middleware import global_exception_handler

logger = logging.getLogger(__name__)

def create_app(mode: str = "web") -> FastAPI:
    """
    create FastAPI app instance
    
    Args:
        mode: Run mode supports "web" or "desktop"
    """
    # Set mode environment variable
    os.environ["CLIPFARM_MODE"] = mode
    
    # configure logs
    logging_config = get_logging_config()
    logging.basicConfig(
        level=getattr(logging, logging_config["level"]),
        format=logging_config["format"],
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logging_config["file"])
        ]
    )
    
    # create FastAPI application
    app = FastAPI(
        title="ClipFarm API",
        description="AI Video Clipping & Studio Processing API",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Set application state
    app.state.mode = mode
    
    # configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Production environment requires configuration of specific domain name
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "content-disposition", "Accept-Ranges", "Content-Length"],
    )
    
    # Register global exception handler
    app.add_exception_handler(Exception, global_exception_handler)
    
    # startup event
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"Starting ClipFarm API Service (mode: {mode})...")
        
        # Import all models to ensure tables are created
        Base.metadata.create_all(bind=engine)
        logger.info("Database table creation complete")

        # Auto-sync existing projects from disk if database is empty
        try:
            from backend.core.database import SessionLocal
            from backend.models.project import Project
            from backend.services.data_sync_service import DataSyncService
            from backend.core.config import get_data_directory
            with SessionLocal() as db_session:
                if db_session.query(Project).count() == 0:
                    data_dir = get_data_directory()
                    sync_service = DataSyncService(db_session)
                    sync_service.sync_all_projects_from_filesystem(data_dir)
                    db_session.commit()
                    logger.info("Automatically synced filesystem projects into database on startup")
        except Exception as sync_err:
            logger.warning(f"Project startup auto-sync skipped: {sync_err}")
        
        # load API Key to environment variable
        api_key = get_api_key()
        if api_key:
            os.environ["DASHSCOPE_API_KEY"] = api_key
            logger.info("API Key loaded into environment variable")
        else:
            logger.warning("not found API secret configuration")
        
        # Initialize differently based on mode
        if mode == "desktop":
            logger.info("Desktop mode: use local queue and SQLite")
        else:
            logger.info("Web Mode: Using Redis/Celery")
        
        logger.info("WebSocket Gateway service is disabled; using new simplified progress system")
    
    # shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down ClipFarm API service...")
        logger.info("WebSocket Gateway service is disabled")
    
    # register routes
    app.include_router(health_router, prefix="/api/health", tags=["health"])
    app.include_router(api_router, prefix="/api/v1")
    
    # add video-categories Route (unified to api_router in progress)
    @app.get("/api/v1/video-categories")
    async def get_video_categories():
        """Get video classification configuration."""
        from .core.shared_config import VIDEO_CATEGORIES_CONFIG
        categories_list = []
        for cat, meta in VIDEO_CATEGORIES_CONFIG.items():
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
    
    # Root health check endpoint
    @app.get("/health")
    async def root_health():
        try:
            return {
                "status": "ok",
                "mode": mode,
                "version": "1.0.0"
            }
        except Exception as e:
            return JSONResponse(
                status_code=500, 
                content={"status": "error", "detail": str(e)}
            )
    
    return app
