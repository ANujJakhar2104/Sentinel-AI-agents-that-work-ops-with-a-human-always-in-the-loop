"""Celery tasks for agent execution"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import select, and_

from app.tasks.celery_app import celery_app
from app.database import async_session_maker
from app.models.db_models import Task, TaskStatus
from app.agents.orchestrator import OrchestratorAgent
from app.services.audit import AuditService
from app.tools.registry import register_all_tools

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async function in sync context for Celery"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.agent_tasks.process_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_task(self, task_id: str) -> Dict[str, Any]:
    """
    Process a task using the orchestrator agent.

    Args:
        task_id: UUID of the task to process

    Returns:
        Result of task processing
    """
    return run_async(_process_task_async(task_id))


async def _process_task_async(task_id: str) -> Dict[str, Any]:
    """Async implementation of task processing"""
    # Register tools
    register_all_tools()

    async with async_session_maker() as session:
        # Get task
        result = await session.execute(select(Task).where(Task.id == UUID(task_id)))
        task = result.scalar_one_or_none()

        if not task:
            logger.error(f"Task not found: {task_id}")
            return {"error": "Task not found", "task_id": task_id}

        # Check if task is already being processed
        if task.status not in (TaskStatus.PENDING, TaskStatus.FAILED):
            logger.warning(f"Task {task_id} is not in processable state: {task.status}")
            return {
                "error": "Task not in processable state",
                "task_id": task_id,
                "status": task.status.value,
            }

        # Update status
        task.status = TaskStatus.CLASSIFYING
        task.started_at = datetime.utcnow()
        await session.commit()

        try:
            # Create audit service
            audit_service = AuditService(session)

            # Create orchestrator
            orchestrator = OrchestratorAgent(
                task_id=task.id, audit_service=audit_service
            )

            # Prepare context
            context = {
                "input": task.input,
                "task_id": str(task.id),
                "priority": task.priority,
                "metadata": task.metadata,
                "current_state": task.current_state,
                "state_history": task.state_history,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
            }

            # Run orchestrator
            result = await orchestrator.run(context)

            # Update task with results
            task.output = result
            task.current_state = orchestrator.state_machine.current_state.value
            task.state_history = orchestrator.state_machine.to_dict()["history"]

            # Determine final status
            if result.get("status") == "completed":
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
            elif result.get("status") == "escalated":
                task.status = TaskStatus.ESCALATED
            elif result.get("status") == "failed":
                task.status = TaskStatus.FAILED
                task.error = str(result.get("error", "Unknown error"))

            # Store classification if available
            if "classification" in result:
                task.classification = result["classification"]
                task.confidence_score = result["classification"].get("confidence")
                task.task_type = result["classification"].get("task_type")

            await session.commit()

            return {
                "task_id": str(task.id),
                "status": task.status.value,
                "result": result,
            }

        except Exception as e:
            logger.error(f"Task processing failed: {task_id} - {e}")

            # Update task as failed
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.retry_count += 1
            await session.commit()

            raise


@celery_app.task(name="app.tasks.agent_tasks.retry_task")
def retry_task(task_id: str, reason: str = "") -> Dict[str, Any]:
    """Retry a failed task"""
    return run_async(_retry_task_async(task_id, reason))


async def _retry_task_async(task_id: str, reason: str) -> Dict[str, Any]:
    """Async implementation of task retry"""
    async with async_session_maker() as session:
        result = await session.execute(select(Task).where(Task.id == UUID(task_id)))
        task = result.scalar_one_or_none()

        if not task:
            return {"error": "Task not found"}

        if task.retry_count >= task.max_retries:
            return {"error": "Max retries exceeded"}

        # Reset task for retry
        task.status = TaskStatus.PENDING
        task.current_state = "pending"
        task.error = None

        await session.commit()

        # Queue the task again
        process_task.delay(task_id)

        return {
            "task_id": str(task.id),
            "status": "requeued",
            "retry_count": task.retry_count,
            "reason": reason,
        }


@celery_app.task(name="app.tasks.agent_tasks.cancel_task")
def cancel_task(task_id: str, reason: str = "") -> Dict[str, Any]:
    """Cancel a pending or running task"""
    return run_async(_cancel_task_async(task_id, reason))


async def _cancel_task_async(task_id: str, reason: str) -> Dict[str, Any]:
    """Async implementation of task cancellation"""
    async with async_session_maker() as session:
        result = await session.execute(select(Task).where(Task.id == UUID(task_id)))
        task = result.scalar_one_or_none()

        if not task:
            return {"error": "Task not found"}

        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return {"error": f"Cannot cancel task in {task.status.value} state"}

        task.status = TaskStatus.CANCELLED
        task.error = reason or "Cancelled by user"
        task.completed_at = datetime.utcnow()

        await session.commit()

        return {"task_id": str(task.id), "status": "cancelled", "reason": reason}


@celery_app.task(name="app.tasks.agent_tasks.cleanup_expired_tasks")
def cleanup_expired_tasks() -> Dict[str, Any]:
    """Cleanup tasks that have been pending for too long"""
    return run_async(_cleanup_expired_tasks_async())


async def _cleanup_expired_tasks_async() -> Dict[str, Any]:
    """Async implementation of cleanup"""
    async with async_session_maker() as session:
        # Find tasks pending for more than 1 hour
        cutoff = datetime.utcnow() - timedelta(hours=1)

        result = await session.execute(
            select(Task).where(
                and_(Task.status == TaskStatus.PENDING, Task.created_at < cutoff)
            )
        )
        expired_tasks = result.scalars().all()

        count = 0
        for task in expired_tasks:
            task.status = TaskStatus.FAILED
            task.error = "Task expired (pending too long)"
            count += 1

        await session.commit()

        return {"cleaned_up": count, "cutoff": cutoff.isoformat()}
