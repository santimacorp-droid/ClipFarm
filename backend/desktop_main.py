"""
Desktop mode main startup file app_factory Create app, supports port auto-allocation
"""
import os
import sys
import logging
import signal
import socket
import threading
import time
import uvicorn
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI

# Adding project root directory toPythonPath
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.path_utils import get_default_app_data_dir

app_data_dir = get_default_app_data_dir()
app_data_dir.mkdir(parents=True, exist_ok=True)
(app_data_dir / "logs").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("CLIPFARM_APP_DIR", str(app_data_dir))
os.environ.setdefault("AUTOCLIP_APP_DIR", str(app_data_dir))
os.environ.setdefault("CLIPFARM_DATA_DIR", str(app_data_dir))
os.environ.setdefault("AUTOCLIP_DATA_DIR", str(app_data_dir))

db_file = app_data_dir / "clipfarm.db"
legacy_db = app_data_dir / "autoclip.db"
if not db_file.exists() and legacy_db.exists():
    try:
        import shutil
        shutil.copy2(legacy_db, db_file)
    except Exception:
        db_file = legacy_db

os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_file}")
os.environ.setdefault("LOG_FILE", str(app_data_dir / "logs" / "backend.log"))

from backend.app_factory import create_app
from backend.core.desktop_config import (
    get_desktop_config, 
    is_desktop_mode, 
    ensure_desktop_directories
)

class DesktopServiceManager:
    """Desktop service manager, unified managementFastAPIandCeleryservice"""
    
    def __init__(self):
        self.config = get_desktop_config()
        self.app: Optional[FastAPI] = None
        self.celery_app = None
        self.celery_worker = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.start_time: Optional[float] = None
        self.actual_port: Optional[int] = None
        
        # ensure directory exists
        if not ensure_desktop_directories():
            raise RuntimeError("Failed to create desktop directory")

        # Set logging
        self._setup_logging()
    
    def _setup_logging(self):
        """set log configuration"""
        from logging.handlers import RotatingFileHandler
        log_path = self.config.paths.data_dir / "logs" / "clipfarm.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                RotatingFileHandler(str(log_path), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _create_fastapi_app(self) -> FastAPI:
        """CreatingFastAPIapplying"""
        # Using unified app_factory
        app = create_app(mode="desktop")
        
        # Adding desktop-specific route
        @app.get("/desktop/info")
        async def desktop_info():
            """desktop app information"""
            return {
                "app_name": self.config.app_name,
                "app_version": self.config.app_version,
                "data_dir": str(self.config.paths.data_dir),
                "config": self.config.dict()
            }
        
        return app
    
    def _start_celery_worker(self):
        """startingCelery Worker"""
        try:
            from backend.desktop_celery import celery_app
            import subprocess
            import os
            
            self.celery_app = celery_app

            if getattr(sys, "frozen", False):
                def run_worker():
                    celery_app.worker_main([
                        "worker",
                        "--loglevel=" + self.config.log_level.lower(),
                        "--concurrency=1",
                        "--pool=solo",
                    ])

                self.celery_worker_thread = threading.Thread(
                    target=run_worker,
                    daemon=True,
                )
                self.celery_worker_thread.start()
                self.logger.info("✅ Celery Worker Successfully started in frozen runtime thread mode")
                return
            
            # usingsubprocessstartingCelery Worker, Avoid signal handling conflicts
            self.celery_worker_process = subprocess.Popen([
                sys.executable, '-m', 'celery', '-A', 'backend.desktop_celery', 'worker',
                '--loglevel=' + self.config.log_level.lower(),
                '--concurrency=' + str(self.config.celery_worker_concurrency),
                '--quiet=False'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, "AUTOCLIP_DESKTOP_MODE": "true", "AUTOCLIP_MODE": "desktop"})
            
            self.logger.info("✅ Celery Worker Started successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Celery Worker Failed to start: {e}")
            raise
    
    def _start_fastapi_server(self):
        """startingFastAPIServer"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.config.host, 0))
            server_socket.listen(128)
            self.actual_port = server_socket.getsockname()[1]

            config = uvicorn.Config(
                self.app,
                host=self.config.host,
                port=self.actual_port,
                log_level=self.config.log_level.lower(),
                access_log=False
            )
            server = uvicorn.Server(config)

            # output port info to stdout(providing Rust reading)
            print(f"PORT={self.actual_port}", flush=True)
            print(f"BACKEND_URL=http://{self.config.host}:{self.actual_port}", flush=True)
            
            # Writing port to file (fallback option)
            port_file = self.config.paths.data_dir / "backend.port"
            with open(port_file, 'w') as f:
                f.write(str(self.actual_port))
            
            self.logger.info(f"🚀 Backend service started on port: {self.actual_port}")
            
            # Running server
            server.run(sockets=[server_socket])
            
        except Exception as e:
            self.logger.error(f"❌ FastAPI failed to start server: {e}")
            print(f"BACKEND_ERROR={e}", flush=True)
            self.is_running = False
            if getattr(self, "celery_worker_process", None):
                self.celery_worker_process.terminate()
                self.celery_worker_process = None
            raise
    
    def start(self):
        """start all services"""
        if self.is_running:
            self.logger.warning("service is already running")
            return
        
        try:
            self.start_time = time.time()
            
            # CreatingFastAPIapplying
            self.app = self._create_fastapi_app()
            
            # startingCelery Worker
            self._start_celery_worker()
            
            self.is_running = True

            # startingFastAPIServer
            self.server_thread = threading.Thread(
                target=self._start_fastapi_server,
                daemon=True
            )
            self.server_thread.start()
            
            self.logger.info(f"🚀 AutoClip Desktop service started successfully")
            self.logger.info(f"🌐 APIAddress: http://{self.config.host}:<dynamic>")
            
        except Exception as e:
            self.logger.error(f"❌ service startup failed: {e}")
            self.stop()
            raise
    
    def stop(self):
        """stop all services"""
        if not self.is_running:
            return
        
        try:
            self.logger.info("🛑 stopping service......")
            
            # stoppingCelery WorkerProcess
            if hasattr(self, 'celery_worker_process') and self.celery_worker_process:
                try:
                    self.celery_worker_process.terminate()
                    # Waiting for process to gracefully exit
                    try:
                        self.celery_worker_process.wait(timeout=5)
                        self.logger.info("✅ Celery Worker Already stopped")
                    except subprocess.TimeoutExpired:
                        self.logger.warning("Celery Worker Unable to terminate within5Stopping within 10 seconds, forcefully terminating")
                        self.celery_worker_process.kill()
                        self.celery_worker_process.wait()
                except Exception as e:
                    self.logger.error(f"stoppingCelery Workerfailed: {e}")
                finally:
                    self.celery_worker_process = None

            if hasattr(self, 'celery_worker_thread') and self.celery_worker_thread:
                self.celery_worker_thread = None
            
            # stoppingFastAPIServer - Use graceful shutdown instead of sending signal
            if self.server_thread and self.server_thread.is_alive():
                # Waiting for server thread to exit naturally
                self.server_thread.join(timeout=5)
                if self.server_thread.is_alive():
                    self.logger.warning("Server thread failed to start within5Terminated within seconds")
            
            self.is_running = False
            self.start_time = None
            self.logger.info("✅ Service stopped")
            
        except Exception as e:
            self.logger.error(f"❌ failed to stop service: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """get service status"""
        return {
            "is_running": self.is_running,
            "start_time": self.start_time,
            "uptime": time.time() - self.start_time if self.start_time else 0,
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "debug": self.config.debug_mode,
                "version": self.config.app_version
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Health check"""
        try:
            import requests
            port = self.actual_port or self.config.port
            response = requests.get(
                f"http://{self.config.host}:{port}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response": response.json(),
                    "port": port
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "port": port
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "port": self.actual_port or self.config.port
            }

# Global service manager instance
service_manager = None

def get_service_manager() -> DesktopServiceManager:
    """Getting service manager instance"""
    global service_manager
    if service_manager is None:
        service_manager = DesktopServiceManager()
    return service_manager

def main():
    """Main function"""
    # Setting desktop mode environment variables
    os.environ["AUTOCLIP_DESKTOP_MODE"] = "true"
    os.environ["AUTOCLIP_MODE"] = "desktop"
    
    # check desktop mode
    if not is_desktop_mode():
        print("❌ This application runs only in desktop mode")
        sys.exit(1)
    
    # get service manager
    manager = get_service_manager()
    config = manager.config
    
    print(f"🚀 starting AutoClip Desktop v{config.app_version}")
    print(f"📁 Data directory: {config.paths.data_dir}")
    print(f"🌐 Service address: http://{config.host}:0 (auto-assign port)")
    
    # set signal handling
    def signal_handler(signum, frame):
        print(f"\n🛑 received stop signal ({signum}), Shutting down service...")
        if manager.is_running:
            manager.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Starting service
        manager.start()
        
        # keep main thread running
        while manager.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal, shutting down service...")
        manager.stop()
    except Exception as e:
        print(f"❌ service run failed: {e}")
        manager.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
