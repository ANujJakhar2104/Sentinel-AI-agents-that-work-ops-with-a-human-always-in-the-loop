"""SQLAlchemy database models"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    ForeignKey,
    DateTime,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.database import Base


class TaskStatus(str, enum.Enum):
    """Task status enumeration"""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    EXECUTING = "executing"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, enum.Enum):
    """Task priority levels (1 = highest, 10 = lowest)"""

    CRITICAL = 1
    HIGH = 2
    MEDIUM_HIGH = 3
    MEDIUM = 5
    LOW = 7
    LOWEST = 10


class ToolExecutionStatus(str, enum.Enum):
    """Tool execution status"""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class Task(Base):
    """Task model - represents a unit of work for agents"""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False
    )
    task_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)

    # Input/Output
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification results
    classification: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # State Machine
    current_state: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )
    state_history: Mapped[list] = mapped_column(JSONB, default=list)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    thoughts: Mapped[List["AgentThought"]] = relationship(
        "AgentThought",
        back_populates="task",
        lazy="selectin",
        order_by="AgentThought.created_at",
    )
    tool_executions: Mapped[List["ToolExecution"]] = relationship(
        "ToolExecution",
        back_populates="task",
        lazy="selectin",
        order_by="ToolExecution.created_at",
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, status={self.status}, type={self.task_type})>"


class AgentThought(Base):
    """Agent thoughts and actions for audit trail"""

    __tablename__ = "agent_thoughts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE")
    )

    # Agent Info
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Thought Process (ReAct pattern)
    thought: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action_input: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    observation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Execution Details
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Additional Context
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="thoughts")
    tool_executions: Mapped[List["ToolExecution"]] = relationship(
        "ToolExecution", back_populates="thought", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AgentThought(id={self.id}, agent={self.agent_name}, action={self.action})>"


class ToolExecution(Base):
    """Tool execution records for audit trail"""

    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE")
    )
    thought_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_thoughts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Tool Info
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tool_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Execution Status
    status: Mapped[ToolExecutionStatus] = mapped_column(
        SQLEnum(ToolExecutionStatus),
        default=ToolExecutionStatus.PENDING,
        nullable=False,
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Error Handling
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="tool_executions")
    thought: Mapped[Optional["AgentThought"]] = relationship(
        "AgentThought", back_populates="tool_executions"
    )

    def __repr__(self) -> str:
        return f"<ToolExecution(id={self.id}, tool={self.tool_name}, status={self.status})>"
