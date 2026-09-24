"""
Single backend application factory function web and desktop two modes
"""
import logging
import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.v1 import api_router
from backend.api.v1.health import router as health_router
from backend.core.database import engine
from backend.models.base import Base
from backend.core.config import get_logging_config, get_api_key
from backend.core.error_middleware import global_exception_handler

logger = logging.getLogger(__name__)

def create_app(mode: Optional[str] = None) -> FastAPI:
    """
    create FastAPI app instance
    
    Args:
        mode: Run mode supports "desktop" (default standalone) or "web"
    """
    if mode is None:
        mode = os.environ.get("CLIPFARM_MODE", "desktop")
    
    # Set mode environment variable
    os.environ["CLIPFARM_MODE"] = mode
    
    # configure logs
    try:
        from logging.handlers import RotatingFileHandler
        logging_config = get_logging_config()
        log_file = Path(logging_config["file"])
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(str(log_file), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        handlers = [logging.StreamHandler(), file_handler]
    except Exception:
        handlers = [logging.StreamHandler()]
        logging_config = {"level": "INFO", "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}

    logging.basicConfig(
        level=getattr(logging, logging_config.get("level", "INFO")),
        format=logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=handlers,
        force=True
    )
    
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
        
        # Recover any projects left in "processing" state due to previous abrupt app termination
        try:
            from backend.core.database import SessionLocal
            from backend.models.project import Project, ProjectStatus
            with SessionLocal() as db_session:
                stuck_projects = db_session.query(Project).filter(Project.status == ProjectStatus.PROCESSING).all()
                if stuck_projects:
                    for proj in stuck_projects:
                        proj.status = ProjectStatus.FAILED
                        cfg = dict(proj.processing_config or {})
                        cfg["error_message"] = "Processing was interrupted by an application shutdown. Click Retry to re-run."
                        proj.processing_config = cfg
                    db_session.commit()
                    logger.info(f"Recovered {len(stuck_projects)} interrupted project(s) on startup")
        except Exception as rec_err:
            logger.warning(f"Startup crash recovery skipped: {rec_err}")

        # Auto-clean stale temporary files/directories older than 2 hours
        try:
            import time
            import shutil
            from backend.core.config import get_temp_directory
            temp_dir = get_temp_directory()
            if temp_dir.exists():
                cutoff = time.time() - (2 * 3600)  # 2 hours
                cleaned_count = 0
                for item in temp_dir.iterdir():
                    try:
                        if item.stat().st_mtime < cutoff:
                            if item.is_dir():
                                shutil.rmtree(item, ignore_errors=True)
                            else:
                                item.unlink(missing_ok=True)
                            cleaned_count += 1
                    except Exception:
                        pass
                if cleaned_count > 0:
                    logger.info(f"Cleaned {cleaned_count} stale temporary file(s)/folder(s) from {temp_dir}")
        except Exception as cleanup_err:
            logger.warning(f"Startup temp cleanup skipped: {cleanup_err}")

        # load API Key to environment variable
        api_key = get_api_key()
        if api_key:
            os.environ["DASHSCOPE_API_KEY"] = api_key
            logger.info("API Key loaded into environment variable")
        else:
            logger.warning("not found API secret configuration")
        
        # Initialize standalone desktop engine
        logger.info(f"ClipFarm standalone desktop engine active (mode: {mode}) with local SQLite and direct task execution")
        logger.info("Progress system active: direct database polling")

        yield

        logger.info("Shutting down ClipFarm API service...")
        logger.info("WebSocket Gateway service is disabled")

    # create FastAPI application
    app = FastAPI(
        title="ClipFarm API",
        description="AI Video Clipping & Studio Processing API",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
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

    # Mount frontend static distribution if available (Single-Port App Mode)
    dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if (dist_dir / "index.html").is_file():
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        
        @app.get("/")
        async def serve_index():
            return FileResponse(dist_dir / "index.html")

        @app.get("/{full_path:path}")
        async def serve_frontend_spa(full_path: str):
            # Never intercept API, docs, or health endpoints
            if not full_path:
                return FileResponse(dist_dir / "index.html")
            if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
                raise HTTPException(status_code=404, detail="Not Found")
            
            target = (dist_dir / full_path).resolve()
            if target.is_relative_to(dist_dir.resolve()) and target.is_file():
                return FileResponse(target)
            return FileResponse(dist_dir / "index.html")
        logger.info(f"Mounted frontend static UI distribution from {dist_dir}")
    else:
        logger.warning(f"Frontend dist not found at {dist_dir}; UI serving disabled.")
    
    return app

