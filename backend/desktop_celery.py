"""
Desktop modeCeleryConfiguration UseSQLiteasBrokerandBackend, Suitable for standalone desktop applications
"""
import os

from pathlib import Path
from backend.core.path_utils import is_desktop_mode, get_default_app_data_dir

from celery import Celery

# File system broker + sqlite backend
app_dir = get_default_app_data_dir()
app_dir.mkdir(parents=True, exist_ok=True)

# CreateCeleryDirectory
celery_dir = app_dir / "celery"
celery_dir.mkdir(parents=True, exist_ok=True)
(celery_dir / "in").mkdir(exist_ok=True)
(celery_dir / "out").mkdir(exist_ok=True)
(celery_dir / "processed").mkdir(exist_ok=True)

celery_app = Celery(
    "autoclip_desktop",
    broker="filesystem://",
    backend=f"db+sqlite:///{app_dir}/celery/results.sqlite3",
)

celery_app.conf.update(
    broker_transport_options={"data_folder_in": str(app_dir / "celery" / "in"),
                              "data_folder_out": str(app_dir / "celery" / "out"),
                              "data_folder_processed": str(app_dir / "celery" / "processed")},
    task_ignore_result=False,
)

if __name__ == '__main__':
    celery_app.start()
