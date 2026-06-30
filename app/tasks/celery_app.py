"""Celery application configuration"""

from celery import Celery
from celery.signals import task_prerun, task_postrun

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "agentic_ops",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.agent_tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.task_timeout_seconds + 60,  # Hard limit
    task_soft_time_limit=settings.task_timeout_seconds,  # Soft limit
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    # Worker settings
    worker_prefetch_multiplier=1,  # One task per worker at a time
    worker_concurrency=2,
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=settings.max_task_retries,
    # Beat schedule (for periodic tasks)
    beat_schedule={
        "cleanup-expired-tasks": {
            "task": "app.tasks.agent_tasks.cleanup_expired_tasks",
            "schedule": 3600.0,  # Every hour
        },
    },
)


# Signal handlers for logging
@task_prerun.connect
def task_prerun_handler(
    sender=None, task_id=None, task=None, args=None, kwargs=None, **extra
):
    """Log task start"""
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Task started: {task.name} [{task_id}]")


@task_postrun.connect
def task_postrun_handler(
    sender=None,
    task_id=None,
    task=None,
    args=None,
    kwargs=None,
    retval=None,
    state=None,
    **extra,
):
    """Log task completion"""
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Task completed: {task.name} [{task_id}] - State: {state}")
