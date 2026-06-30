"""Health check endpoints"""

from fastapi import APIRouter, Depends
from datetime import datetime

from app.database import check_db_connection
from app.config import get_settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns the health status of all system components.
    """
    db_status = "connected" if await check_db_connection() else "disconnected"

    # Check Redis connection
    redis_status = "connected"
    try:
        import redis

        r = redis.from_url(settings.redis_url)
        r.ping()
    except Exception:
        redis_status = "disconnected"

    # Check Celery workers
    from app.tasks.celery_app import celery_app

    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        workers = len(active) if active else 0
    except Exception:
        workers = 0

    return HealthResponse(
        status="healthy"
        if db_status == "connected" and redis_status == "connected"
        else "degraded",
        database=db_status,
        redis=redis_status,
        workers=workers,
        version="0.1.0",
    )


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """Root endpoint - same as health check"""
    return await health_check()
