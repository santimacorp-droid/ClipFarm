"""
Task module
Contains all asynchronous task definitions
"""

# Remove wildcard imports to avoid early triggering of celery_app import chain

__all__ = [
    # Processing tasks
    'process_video_pipeline',
    'process_single_step',
    'retry_processing_step',
    
    # Video tasks
    'extract_video_clips',
    'generate_video_collections',
    'optimize_video_quality',
    
    # Notification tasks
    'send_processing_notification',
    'send_error_notification',
    'send_completion_notification',
    
    # Maintenance tasks
    'cleanup_expired_tasks',
    'health_check',
    'backup_project_data',
    
    # Data cleaning tasks
    'cleanup_expired_data',
    'check_data_consistency',
    'cleanup_orphaned_data',
    
    # Submission tasks
    'upload_clip_task',
    'batch_upload_task'
] 