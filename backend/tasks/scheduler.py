"""
Periodic task scheduler
Configure and manage regularly scheduled maintenance tasks
"""

import logging
from celery import Celery
from celery.schedules import crontab

from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)


# Configure periodic task
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Configure periodic task"""
    
    # Execute data cleanup at 2:00 AM daily
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        cleanup_expired_data.s(days=30),
        name='daily_data_cleanup'
    )
    
    # Execute data consistency check hourly
    sender.add_periodic_task(
        crontab(minute=0),
        check_data_consistency.s(),
        name='hourly_consistency_check'
    )
    
    # Purge stale data (retaining 30 days)
    sender.add_periodic_task(
        crontab(hour=3, minute=0, day_of_week=0),
        cleanup_orphaned_data.s(),
        name='weekly_orphaned_cleanup'
    )
    
    # Execute system health check at 1:00 AM daily
    sender.add_periodic_task(
        crontab(hour=1, minute=0),
        health_check.s(),
        name='daily_health_check'
    )
    
    logger.info("Periodic task configuration complete")


def get_scheduled_tasks() -> dict:
    """Get all configured periodic tasks"""
    return {
        'daily_data_cleanup': {
            'schedule': 'Every day at 2:00 AM',
            'task': 'cleanup_expired_data',
            'description': 'Purge expired data (retain 30 days))'
        },
        'hourly_consistency_check': {
            'schedule': 'Hourly',
            'task': 'check_data_consistency',
            'description': 'Data consistency check'
        },
        'weekly_orphaned_cleanup': {
            'schedule': 'Every Sunday at 3:00 AM',
            'task': 'cleanup_orphaned_data',
            'description': 'Purge orphaned data'
        },
        'daily_health_check': {
            'schedule': 'Every day at 1:00 AM',
            'task': 'health_check',
            'description': 'System health check'
        }
    }


def enable_scheduled_tasks():
    """Enable periodic task"""
    try:
        # Add logic here to enable periodic tasks
        logger.info("Periodic task enabled")
        return True
    except Exception as e:
        logger.error(f"Failed to enable periodic task: {e}")
        return False


def disable_scheduled_tasks():
    """Disable periodic task"""
    try:
        # Add logic here to disable periodic tasks
        logger.info("Periodic task disabled")
        return True
    except Exception as e:
        logger.error(f"Failed to disable periodic task: {e}")
        return False
