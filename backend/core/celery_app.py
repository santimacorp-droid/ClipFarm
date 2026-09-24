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
    timezone = 'UTC'
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


def should_run_locally() -> bool:
    """Determine whether tasks should execute in a local background thread.
    
    In ClipFarm standalone / desktop software, tasks execute in local background threads
    by default so that video processing never stalls waiting on an external queue.
    Celery execution is only enabled when explicitly opted in via USE_CELERY=true or CLIPFARM_USE_CELERY=true.
    """
    # Explicit override: Force Celery
    force_celery = (
        os.getenv("USE_CELERY", "").lower() in {"1", "true", "yes"}
        or os.getenv("CLIPFARM_USE_CELERY", "").lower() in {"1", "true", "yes"}
    )
    if force_celery:
        return False

    # Default to True for all local desktop/standalone usage and testing.
    # This prevents third-party or unrelated Redis instances on localhost:6379 from hijacking ClipFarm tasks.
    return True


class _LocalAsyncResult:
    """A lightweight substitute for `AsyncResult`, returned when tasks run locally in a background thread."""

    def __init__(self, task_id: str):
        self.id = task_id
        self.task_id = task_id
        self.state = "PENDING"

    def get(self, *args, **kwargs):
        return None

    def ready(self) -> bool:
        return False


from concurrent.futures import ThreadPoolExecutor

# Dedicated bounded worker pool for local desktop task execution (max 2 concurrent heavy video tasks)
_LOCAL_TASK_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="clipfarm-task")

class DesktopAwareTask(celery_app.Task):
    """Zero-Redis capable task runner.

    When running in desktop/standalone mode or when no Redis broker is available,
    tasks execute asynchronously in a background worker pool with SQLite persistence.
    If Redis fails at dispatch time, it gracefully falls back to local execution.
    """

    def apply_async(self, args=None, kwargs=None, task_id=None, **options):
        import uuid

        tid = task_id or str(uuid.uuid4())
        call_args = list(args) if args else []
        call_kwargs = dict(kwargs) if kwargs else {}

        def _run_locally():
            def _thread_target():
                try:
                    self.apply(args=call_args, kwargs=call_kwargs, task_id=tid)
                except Exception as exc:  # noqa: BLE001
                    import logging
                    logging.getLogger(__name__).error(
                        f"Local in-process task failed: {self.name} ({tid}): {exc}", exc_info=True
                    )

            _LOCAL_TASK_EXECUTOR.submit(_thread_target)
            return _LocalAsyncResult(tid)

        if should_run_locally():
            return _run_locally()

        try:
            return super().apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)
        except Exception as broker_exc:
            import logging
            logging.getLogger(__name__).warning(
                f"Celery broker dispatch failed ({broker_exc}); falling back to local execution for {self.name} ({tid})"
            )
            return _run_locally()


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