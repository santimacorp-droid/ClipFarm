"""
CeleryApp configuration
Task queue configuration and initialization.
"""

import os
from celery import Celery
from celery.schedules import crontab
from pathlib import Path

# Sets the default configuration module.
# os.environ.setdefault('CELERY_CONFIG_MODULE', 'backend.core.celery_app')

# Creates a Celery application instance.
celery_app = Celery('autoclip')

# Configures Celery.
class CeleryConfig:
    """CeleryConfiguration class"""
    
    # Specifies the task serialization format.
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    timezone = 'Asia/Shanghai'
    enable_utc = True
    
    # Redis configuration settings.
    broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Task configuration
    task_always_eager = os.getenv('CELERY_ALWAYS_EAGER', 'False').lower() == 'true'  # Performs asynchronous execution in production environments.
    task_eager_propagates = True
    
    # Worker process configurations.
    worker_prefetch_multiplier = 1
    worker_max_tasks_per_child = 1000
    worker_disable_rate_limits = True
    worker_concurrency = 1  # Force the number of concurrent workers to 1 to prevent duplicate processing.
    
    # Job routing
    task_routes = {
        'backend.tasks.processing.*': {'queue': 'processing'},
        'backend.tasks.video.*': {'queue': 'video'},
        'backend.tasks.notification.*': {'queue': 'notification'},
        'backend.tasks.upload.*': {'queue': 'upload'},  # Adds upload task routing.
        'backend.tasks.import_processing.*': {'queue': 'processing'},  # Imports task routing information.
    }
    
    # Crontab-based scheduling for tasks.
    beat_schedule = {
        'cleanup-expired-tasks': {
            'task': 'backend.tasks.maintenance.cleanup_expired_tasks',
            'schedule': crontab(hour=2, minute=0),  # Runs at 2:00 AM every day.
        },
        'health-check': {
            'task': 'backend.tasks.maintenance.health_check',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
        },
    }
    
    # Result configuration
    result_expires = 3600  # 1Hours
    task_ignore_result = False
    
    # Log configuration
    worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s'

# App configuration
celery_app.config_from_object(CeleryConfig)


def _is_desktop_mode() -> bool:
    return os.getenv("AUTOCLIP_DESKTOP_MODE", "").lower() in {"1", "true", "yes"}


class _LocalAsyncResult:
    """A lightweight substitute for `AsyncResult`, returned when tasks run locally on the desktop in a separate thread.. """

    def __init__(self, task_id: str):
        self.id = task_id
        self.task_id = task_id
        self.state = "PENDING"

    def get(self, *args, **kwargs):
        return None

    def ready(self) -> bool:
        return False


class DesktopAwareTask(celery_app.Task):
    """The desktop installer does not include a Redis broker; in production mode, `core.celery_app` refers to... redis://localhost. 

    All endpoints use... `task.delay(...)` / `apply_async(...)` By default, dispatching a task adds it to...
    Redis Queue —— Because nobody consumes the queue on the desktop, it will always be stuck on... 0%「Initializing」. 

    Here, under desktop mode, change `apply_async` to...「Executes synchronously in a background daemon thread. apply()」: 
    No dependencies on any broker; returns immediately, progress is written to the database for polling by the frontend. The behavior in production mode remains unchanged.. 
    """

    def apply_async(self, args=None, kwargs=None, task_id=None, **options):
        if _is_desktop_mode():
            import threading
            import uuid

            tid = task_id or str(uuid.uuid4())
            call_args = list(args) if args else []
            call_kwargs = dict(kwargs) if kwargs else {}

            def _run():
                try:
                    self.apply(args=call_args, kwargs=call_kwargs, task_id=tid)
                except Exception as exc:  # noqa: BLE001
                    import logging
                    logging.getLogger(__name__).error(
                        f"Local execution of a task fails on the desktop. {self.name} ({tid}): {exc}", exc_info=True
                    )

            threading.Thread(target=_run, name=f"task-{self.name}", daemon=True).start()
            return _LocalAsyncResult(tid)

        return super().apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)


# On the desktop, make all `@celery_app.task` decorators use the local execution base class described above.
celery_app.Task = DesktopAwareTask

# Enables automatic discovery of tasks.
celery_app.autodiscover_tasks([
    'backend.tasks.processing',
    'backend.tasks.video', 
    'backend.tasks.notification',
    'backend.tasks.maintenance',
    'backend.tasks.import_processing'  # Adds import handling task.
])

if __name__ == '__main__':
    celery_app.start()