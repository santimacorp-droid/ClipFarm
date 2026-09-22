"""
Minimal Celery application configuration
Avoid all import issues; provide only basic task processing functionality
"""

import os
import sys
from pathlib import Path
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
    
    # Task Configuration
    task_always_eager=False,
    task_eager_propagates=True,
    
    # Worker process configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=True,
    
    # Result configuration
    result_expires=3600,
    task_ignore_result=False,
    
    # Disable automatic discovery
    autodiscover_tasks=False,
)

# Manual task registration
@celery_app.task(bind=True, name='tasks.processing.process_video_pipeline')
def process_video_pipeline(self, project_id: str, input_video_path: str, input_srt_path: str):
    """Video processing pipeline task"""
    print(f"🎬 Start processing project: {project_id}")
    print(f"📹 Video Path: {input_video_path}")
    print(f"📝 Subtitle path: {input_srt_path}")
    
    # Simulate processing
    import time
    steps = [
        "Outline extraction",
        "Time location", 
        "Content rating",
        "Title Generation",
        "Theme clustering",
        "Video Segmentation"
    ]
    
    for i, step in enumerate(steps):
        progress = (i + 1) * 16  # each step16%
        print(f"📊 Steps {i+1}/6: {step} - {progress}%")
        
        # Update task status
        self.update_state(
            state='PROGRESS',
            meta={
                'current': i + 1,
                'total': 6,
                'status': f'Executing: {step}',
                'progress': progress
            }
        )
        
        time.sleep(2)  # Simulate processing time
    
    print(f"✅ Project {project_id} Processing complete")
    return {
        "success": True,
        "project_id": project_id,
        "message": "Video processing completed",
        "steps": steps
    }

@celery_app.task(bind=True, name='tasks.processing.process_single_step')
def process_single_step(self, project_id: str, step: str, config: dict):
    """Individual processing task"""
    print(f"🔧 Start processing project {project_id} steps of: {step}")
    
    # Simulate processing
    import time
    time.sleep(3)
    
    print(f"✅ Steps {step} Processing complete")
    return {
        "success": True,
        "project_id": project_id,
        "step": step,
        "message": f"Steps {step} Processing complete"
    }

# Compatibility task name
@celery_app.task(bind=True, name='backend.tasks.processing.process_video_pipeline')
def backend_process_video_pipeline(self, project_id: str, input_video_path: str, input_srt_path: str):
    """Backend video processing pipeline task (compatibility))"""
    return process_video_pipeline(self, project_id, input_video_path, input_srt_path)

@celery_app.task(bind=True, name='backend.tasks.processing.process_single_step')
def backend_process_single_step(self, project_id: str, step: str, config: dict):
    """Backend individual processing task (compatibility))"""
    return process_single_step(self, project_id, step, config)

if __name__ == '__main__':
    celery_app.start()

