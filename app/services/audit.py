"""Audit logging service for compliance"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db_models import AgentThought, ToolExecution, ToolExecutionStatus


class AuditService:
    """
    Service for logging agent thoughts and tool executions.

    Every agent thought and action is logged for:
    - Compliance auditing
    - Debugging
    - Performance analysis
    - Training data collection
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize audit service.

        Args:
            session: Database session
        """
        self.session = session

    async def log_thought(
        self,
        task_id: UUID,
        agent_name: str,
        agent_version: Optional[str] = None,
        thought: Optional[str] = None,
        action: Optional[str] = None,
        action_input: Optional[Dict[str, Any]] = None,
        observation: Optional[str] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentThought:
        """
        Log an agent thought/action.

        Args:
            task_id: Task ID
            agent_name: Name of the agent
            agent_version: Version of the agent
            thought: Agent's reasoning
            action: Action taken
            action_input: Input to the action
            observation: Result of the action
            model: LLM model used
            tokens_used: Number of tokens consumed
            latency_ms: Time taken in milliseconds
            metadata: Additional metadata

        Returns:
            Created AgentThought record
        """
        thought_record = AgentThought(
            task_id=task_id,
            agent_name=agent_name,
            agent_version=agent_version,
            thought=thought,
            action=action,
            action_input=action_input or {},
            observation=observation,
            model=model,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            extra_metadata=metadata or {},
        )

        self.session.add(thought_record)
        await self.session.flush()
        await self.session.refresh(thought_record)

        return thought_record

    async def log_tool_execution(
        self,
        task_id: UUID,
        tool_name: str,
        tool_input: Dict[str, Any],
        execution_id: Optional[UUID] = None,
        thought_id: Optional[UUID] = None,
        tool_output: Optional[Dict[str, Any]] = None,
        status: ToolExecutionStatus = ToolExecutionStatus.PENDING,
        approved_by: Optional[str] = None,
        error: Optional[str] = None,
    ) -> ToolExecution:
        """
        Log a tool execution.

        Args:
            task_id: Task ID
            tool_name: Name of the tool
            tool_input: Input to the tool
            execution_id: Optional existing execution ID
            thought_id: Associated thought ID
            tool_output: Output from the tool
            status: Execution status
            approved_by: Who approved the execution
            error: Error message if failed

        Returns:
            Created or updated ToolExecution record
        """
        # Check if execution exists
        if execution_id:
            result = await self.session.execute(
                select(ToolExecution).where(ToolExecution.id == execution_id)
            )
            execution = result.scalar_one_or_none()

            if execution:
                # Update existing execution
                if tool_output is not None:
                    execution.tool_output = tool_output
                if status != ToolExecutionStatus.PENDING:
                    execution.status = status
                    if status in (
                        ToolExecutionStatus.COMPLETED,
                        ToolExecutionStatus.FAILED,
                    ):
                        execution.executed_at = datetime.utcnow()
                if error:
                    execution.error = error
                if approved_by:
                    execution.approved_by = approved_by
                    execution.approved_at = datetime.utcnow()

                await self.session.flush()
                await self.session.refresh(execution)
                return execution

        # Create new execution
        execution = ToolExecution(
            id=execution_id,
            task_id=task_id,
            thought_id=thought_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            status=status,
            approved_by=approved_by,
            approved_at=datetime.utcnow() if approved_by else None,
            executed_at=datetime.utcnow()
            if status == ToolExecutionStatus.COMPLETED
            else None,
            error=error,
        )

        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)

        return execution

    async def get_task_thoughts(self, task_id: UUID) -> list:
        """Get all thoughts for a task"""
        result = await self.session.execute(
            select(AgentThought)
            .where(AgentThought.task_id == task_id)
            .order_by(AgentThought.created_at)
        )
        return list(result.scalars().all())

    async def get_task_executions(self, task_id: UUID) -> list:
        """Get all tool executions for a task"""
        result = await self.session.execute(
            select(ToolExecution)
            .where(ToolExecution.task_id == task_id)
            .order_by(ToolExecution.created_at)
        )
        return list(result.scalars().all())

    async def get_task_timeline(self, task_id: UUID) -> list:
        """
        Get a combined timeline of thoughts and executions.

        Returns events sorted by timestamp.
        """
        thoughts = await self.get_task_thoughts(task_id)
        executions = await self.get_task_executions(task_id)

        events = []

        for thought in thoughts:
            events.append(
                {
                    "timestamp": thought.created_at,
                    "event_type": "thought",
                    "agent_name": thought.agent_name,
                    "description": thought.thought or f"Action: {thought.action}",
                    "details": {
                        "action": thought.action,
                        "action_input": thought.action_input,
                        "observation": thought.observation,
                        "latency_ms": thought.latency_ms,
                    },
                }
            )

        for execution in executions:
            events.append(
                {
                    "timestamp": execution.created_at,
                    "event_type": "tool_execution",
                    "agent_name": None,
                    "description": f"Tool: {execution.tool_name}",
                    "details": {
                        "tool_name": execution.tool_name,
                        "status": execution.status.value,
                        "output": execution.tool_output,
                        "error": execution.error,
                    },
                }
            )

        # Sort by timestamp
        events.sort(key=lambda x: x["timestamp"])

        return events
