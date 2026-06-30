"""Audit log API endpoints"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.db_models import Task, AgentThought, ToolExecution
from app.models.schemas import (
    AgentThoughtListResponse,
    AgentThoughtResponse,
    ToolExecutionListResponse,
    ToolExecutionResponse,
    TaskTimelineResponse,
    TimelineEvent,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/api/audit", tags=["Audit"])


@router.get(
    "/tasks/{task_id}/thoughts",
    response_model=AgentThoughtListResponse,
    summary="Get agent thoughts for a task",
)
async def get_task_thoughts(
    task_id: UUID, db: AsyncSession = Depends(get_db)
) -> AgentThoughtListResponse:
    """
    Get all agent thoughts (reasoning steps) for a task.

    This shows the complete thought process of all agents involved
    in processing the task.
    """
    # Verify task exists
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    # Get thoughts
    audit_service = AuditService(db)
    thoughts = await audit_service.get_task_thoughts(task_id)

    return AgentThoughtListResponse(
        thoughts=[
            AgentThoughtResponse(
                id=t.id,
                task_id=t.task_id,
                agent_name=t.agent_name,
                agent_version=t.agent_version,
                thought=t.thought,
                action=t.action,
                action_input=t.action_input,
                observation=t.observation,
                model=t.model,
                tokens_used=t.tokens_used,
                latency_ms=t.latency_ms,
                created_at=t.created_at,
                metadata=t.metadata,
            )
            for t in thoughts
        ],
        total=len(thoughts),
    )


@router.get(
    "/tasks/{task_id}/executions",
    response_model=ToolExecutionListResponse,
    summary="Get tool executions for a task",
)
async def get_task_executions(
    task_id: UUID, db: AsyncSession = Depends(get_db)
) -> ToolExecutionListResponse:
    """
    Get all tool executions for a task.

    This shows every tool that was executed during task processing,
    along with inputs, outputs, and status.
    """
    # Verify task exists
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    # Get executions
    audit_service = AuditService(db)
    executions = await audit_service.get_task_executions(task_id)

    return ToolExecutionListResponse(
        executions=[
            ToolExecutionResponse(
                id=e.id,
                task_id=e.task_id,
                thought_id=e.thought_id,
                tool_name=e.tool_name,
                tool_input=e.tool_input,
                tool_output=e.tool_output,
                status=e.status,
                approved_by=e.approved_by,
                approved_at=e.approved_at,
                executed_at=e.executed_at,
                error=e.error,
                retry_count=e.retry_count,
                created_at=e.created_at,
            )
            for e in executions
        ],
        total=len(executions),
    )


@router.get(
    "/tasks/{task_id}/timeline",
    response_model=TaskTimelineResponse,
    summary="Get complete task timeline",
)
async def get_task_timeline(
    task_id: UUID, db: AsyncSession = Depends(get_db)
) -> TaskTimelineResponse:
    """
    Get a complete timeline of all events for a task.

    This combines thoughts and tool executions into a chronological
    timeline for full audit visibility.
    """
    # Get task
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found"
        )

    # Get timeline
    audit_service = AuditService(db)
    events = await audit_service.get_task_timeline(task_id)

    # Calculate total duration
    total_duration_ms = None
    if task.completed_at and task.created_at:
        delta = task.completed_at - task.created_at
        total_duration_ms = int(delta.total_seconds() * 1000)

    return TaskTimelineResponse(
        task_id=task_id,
        status=task.status,
        created_at=task.created_at,
        completed_at=task.completed_at,
        events=[
            TimelineEvent(
                timestamp=e["timestamp"],
                event_type=e["event_type"],
                agent_name=e["agent_name"],
                description=e["description"],
                details=e["details"],
            )
            for e in events
        ],
        total_duration_ms=total_duration_ms,
    )
