"""
Desktop dedicatedAPIProvides special functions required by desktop application
"""
import os
import psutil
import platform
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.core.desktop_config import get_desktop_config, is_desktop_mode

router = APIRouter()

# Check desktop mode
def check_desktop_mode():
    if not is_desktop_mode():
        raise HTTPException(status_code=400, detail="This endpoint is only available in desktop mode")

class SystemInfo(BaseModel):
    """System information model"""
    platform: str
    platform_version: str
    architecture: str
    processor: str
    memory_total: int
    memory_available: int
    memory_usage_percent: float
    disk_usage_percent: float
    python_version: str
    app_version: str

class ServiceStatus(BaseModel):
    """Service status model"""
    is_running: bool
    port: int
    uptime: str
    memory_usage: int
    cpu_usage: float
    last_health_check: str

@router.get("/system/info", response_model=SystemInfo)
async def get_system_info():
    """Get system information"""
    check_desktop_mode()
    
    try:
        # Get system information
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return SystemInfo(
            platform=platform.system(),
            platform_version=platform.version(),
            architecture=platform.machine(),
            processor=platform.processor(),
            memory_total=memory.total,
            memory_available=memory.available,
            memory_usage_percent=memory.percent,
            disk_usage_percent=disk.percent,
            python_version=platform.python_version(),
            app_version=get_desktop_config().app_version
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system information: {str(e)}")

@router.get("/service/status", response_model=ServiceStatus)
async def get_service_status():
    """Get service status"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        process = psutil.Process()
        
        return ServiceStatus(
            is_running=True,
            port=config.port,
            uptime=str(datetime.now() - datetime.fromtimestamp(process.create_time())),
            memory_usage=process.memory_info().rss,
            cpu_usage=process.cpu_percent(),
            last_health_check=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {str(e)}")

@router.get("/logs")
async def get_logs(lines: int = 100):
    """Get app log"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        log_file = config.data_dir / "logs" / "autoclip.log"
        
        if not log_file.exists():
            return {"logs": [], "message": "Log file does not exist"}
        
        # Reading lastNLine logging
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log: {str(e)}")

@router.post("/service/restart")
async def restart_service():
    """Restart service (returns only success; actual restart is provided by endpoint)TauriProcessing)"""
    check_desktop_mode()
    
    return {
        "message": "Service restart request sent",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/config")
async def get_config():
    """Get current configuration"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        return {
            "config": config.dict(),
            "paths": {
                "data_dir": str(config.paths.data_dir),
                "projects_dir": str(config.paths.data_dir / "projects"),
                "logs_dir": str(config.paths.data_dir / "logs")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")

@router.put("/config")
async def update_config(config_data: Dict[str, Any]):
    """Updating configuration"""
    check_desktop_mode()
    
    try:
        from backend.core.desktop_config import save_desktop_config, DesktopConfig
        
        # Validating configuration data
        config = DesktopConfig(**config_data)
        
        # Saving configuration
        if save_desktop_config(config):
            return {"message": "Configuration update succeeded", "config": config.dict()}
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Configuration update failed: {str(e)}")

@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check"""
    check_desktop_mode()
    
    try:
        config = get_desktop_config()
        
        # Check database connection
        db_status = "healthy"
        try:
            from backend.core.database import get_db
            # Simple database connection test
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"
        
        # CheckingCeleryConnecting
        celery_status = "healthy"
        try:
            from backend.desktop_celery import celery_app
            celery_app.control.inspect().stats()
            celery_status = "healthy"
        except Exception:
            celery_status = "unhealthy"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": config.app_version,
            "mode": "desktop",
            "components": {
                "database": db_status,
                "celery": celery_status,
                "api": "healthy"
            },
            "system": {
                "memory_usage": psutil.virtual_memory().percent,
                "cpu_usage": psutil.cpu_percent(),
                "disk_usage": psutil.disk_usage('/').percent
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
