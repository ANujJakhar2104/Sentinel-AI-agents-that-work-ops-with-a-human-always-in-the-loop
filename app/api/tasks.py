"""Task management API endpoints"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.database import get_db
from app.models.db_models import Task, TaskStatus
from app.models.schemas import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskCancelResponse,
    TaskRetryResponse,
)
from app.tasks.agent_tasks import process_task, cancel_task, retry_task

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def task_to_response(task: Task) -> TaskResponse:
    """Convert Task model to response schema"""
    return TaskResponse(
        id=task.id,
        status=TaskStatus(task.status.value),
        task_type=task.task_type,
        priority=task.priority,
        input=task.input,
        output=task.output,
        error=task.error,
        classification=task.classification,
        confidence_score=task.confidence_score,
        current_state=task.current_state,
        retry_count=task.retry_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        metadata=task.metadata,
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
)
async def create_task(
    task_data: TaskCreate, db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """
    Create a new task for agent processing.

    The task will be queued and processed asynchronously by the orchestrator.
    """
    # Create task
    task = Task(
        input=task_data.input,
        priority=task_data.priority,
        task_type=task_data.task_type,
        metadata=task_data.metadata or {},
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Queue for processing
    process_task.delay(str(task.id))

    return task_to_response(task)


@router.get("", response_model=TaskListResponse, summary="List tasks")
async def list_tasks(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """
    List tasks with optional filtering.
    """
    query = select(Task)
    conditions = []

    if status:
        try:
            status_enum = TaskStatus(status)
            conditions.append(Task.status == status_enum)
        except ValueError:
            pass

    if task_type:
        conditions.append(Task.task_type == task_type)

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = query
    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Get paginated results
    query = query.offset(skip).limit(limit).order_by(desc(Task.created_at))
    result = await db.execute(query)
    tasks = list(result.scalars().all())

    return TaskListResponse(tasks=[task_to_response(t) for t in tasks], total=total)


@router.get("/{task_id}", response_model=TaskResponse, summary="Get task details")
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)) -> TaskResponse:
    """
    Get details of a specific task.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    return task_to_response(task)


@router.post(
    "/{task_id}/cancel", response_model=TaskCancelResponse, summary="Cancel a task"
)
async def cancel_task_endpoint(
    task_id: UUID,
    reason: str = Query("", description="Reason for cancellation"),
    db: AsyncSession = Depends(get_db),
) -> TaskCancelResponse:
    """
    Cancel a pending or running task.
    """
    # Check task exists
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    # Cancel via Celery
    cancel_result = cancel_task(str(task_id), reason)

    return TaskCancelResponse(
        task_id=task_id,
        status=TaskStatus.CANCELLED,
        message=f"Task cancelled: {reason}",
    )


@router.post(
    "/{task_id}/retry", response_model=TaskRetryResponse, summary="Retry a failed task"
)
async def retry_task_endpoint(
    task_id: UUID,
    reason: str = Query("", description="Reason for retry"),
    db: AsyncSession = Depends(get_db),
) -> TaskRetryResponse:
    """
    Retry a failed task.
    """
    # Check task exists
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    if task.status != TaskStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed tasks can be retried",
        )

    # Retry via Celery
    retry_result = retry_task(str(task_id), reason)

    return TaskRetryResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        retry_count=task.retry_count + 1,
        message="Task queued for retry",
    )
