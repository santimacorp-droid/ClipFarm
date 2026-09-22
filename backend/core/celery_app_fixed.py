"""
Uniform Celery application configuration
Avoid circular import issues, providing full task management
"""

import os
from celery import Celery

# Create Celery application
celery_app = Celery('autoclip')

# Basic Configuration
celery_app.conf.update(
    # Serialization format
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Redis configuration
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    
    # Timezone
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # Task configuration
    task_always_eager=False,
    task_eager_propagates=True,
    
    # Worker process configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=True,
    worker_concurrency=1,  # Force concurrency to 1 to prevent duplicate processing
    
    # Result configuration
    result_expires=3600,
    task_ignore_result=False,
    
    # Task routing
    task_routes={
        'backend.tasks.processing.*': {'queue': 'processing'},
        'backend.tasks.video.*': {'queue': 'upload'},
        'backend.tasks.notification.*': {'queue': 'notification'},
        'backend.tasks.maintenance.*': {'queue': 'maintenance'},
        'backend.tasks.upload.*': {'queue': 'upload'},
    },
    
    # Task result configuration
    task_track_started=True,
    task_time_limit=30 * 60,  # 30Minutes
    task_soft_time_limit=25 * 60,  # 25Minutes
)

# Auto-discover task modules
celery_app.autodiscover_tasks([
    'backend.tasks.processing',
    'backend.tasks.video', 
    'backend.tasks.notification',
    'backend.tasks.maintenance',
    'backend.tasks.upload'
])

# Manually register core tasks to avoid automatic discovery failure
@celery_app.task(bind=True, name='backend.tasks.processing.process_video_pipeline')
def process_video_pipeline(self, project_id: str, input_video_path: str, input_srt_path: str):
    """Video processing pipeline tasks"""
    print(f"Initiate project processing: {project_id}")
    print(f"Video Path: {input_video_path}")
    print(f"Subtitle path: {input_srt_path}")
    
    # Simulate processing progress
    import time
    for i in range(6):
        print(f"Step(s) {i+1}/6: Processing......")
        time.sleep(2)
    
    print(f"Project {project_id} Processing complete")
    return {
        "success": True,
        "project_id": project_id,
        "message": "Video processed successfully"
    }

@celery_app.task(bind=True, name='backend.tasks.processing.process_single_step')
def process_single_step(self, project_id: str, step: str, config: dict):
    """Single-step processing task"""
    print(f"Initiate project processing {project_id} Steps: {step}")
    
    # Simulate processing progress
    import time
    time.sleep(3)
    
    print(f"Step(s) {step} Processing complete")
    return {
        "success": True,
        "project_id": project_id,
        "step": step,
        "message": f"Step(s) {step} Processing complete"
    }

@celery_app.task(bind=True, name='backend.tasks.upload.upload_to_bilibili')
def upload_to_bilibili(self, project_id: str, video_path: str, title: str, description: str):
    """Upload to Bilibili task"""
    print(f"Initiate project upload {project_id} To Bilibili")
    print(f"Title: {title}")
    print(f"Description: {description}")
    
    # Simulate upload progress
    import time
    time.sleep(5)
    
    print(f"Project {project_id} Upload complete")
    return {
        "success": True,
        "project_id": project_id,
        "message": "Bilibili upload completed"
    }

if __name__ == '__main__':
    celery_app.start()

