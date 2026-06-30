"""Pydantic models for request/response schemas"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


# ==================== Enums ====================


class TaskStatus(str, Enum):
    """Task status enumeration"""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    EXECUTING = "executing"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority levels"""

    CRITICAL = 1
    HIGH = 2
    MEDIUM_HIGH = 3
    MEDIUM = 5
    LOW = 7
    LOWEST = 10


class ToolExecutionStatus(str, Enum):
    """Tool execution status"""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# ==================== Health ====================


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = "healthy"
    database: str = "connected"
    redis: str = "connected"
    workers: int = 0
    version: str = "0.1.0"


# ==================== Task Schemas ====================


class TaskCreate(BaseModel):
    """Request to create a new task"""

    input: Dict[str, Any] = Field(..., description="Task input data")
    priority: Optional[int] = Field(
        5, ge=1, le=10, description="Task priority (1=highest)"
    )
    task_type: Optional[str] = Field(None, description="Pre-classified task type")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class TaskResponse(BaseModel):
    """Response for a single task"""

    id: UUID
    status: TaskStatus
    task_type: Optional[str]
    priority: int
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    error: Optional[str]
    classification: Optional[Dict[str, Any]]
    confidence_score: Optional[float]
    current_state: str
    retry_count: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Response for list of tasks"""

    tasks: List[TaskResponse]
    total: int


class TaskCancelResponse(BaseModel):
    """Response for task cancellation"""

    task_id: UUID
    status: TaskStatus
    message: str


class TaskRetryResponse(BaseModel):
    """Response for task retry"""

    task_id: UUID
    status: TaskStatus
    retry_count: int
    message: str


# ==================== Agent Thought Schemas ====================


class AgentThoughtResponse(BaseModel):
    """Response for an agent thought"""

    id: UUID
    task_id: UUID
    agent_name: str
    agent_version: Optional[str]
    thought: Optional[str]
    action: Optional[str]
    action_input: Optional[Dict[str, Any]]
    observation: Optional[str]
    model: Optional[str]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    created_at: datetime
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


class AgentThoughtListResponse(BaseModel):
    """Response for list of agent thoughts"""

    thoughts: List[AgentThoughtResponse]
    total: int


# ==================== Tool Execution Schemas ====================


class ToolExecutionResponse(BaseModel):
    """Response for a tool execution"""

    id: UUID
    task_id: UUID
    thought_id: Optional[UUID]
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]]
    status: ToolExecutionStatus
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    executed_at: Optional[datetime]
    error: Optional[str]
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ToolExecutionListResponse(BaseModel):
    """Response for list of tool executions"""

    executions: List[ToolExecutionResponse]
    total: int


class ToolExecuteRequest(BaseModel):
    """Request to execute a tool directly"""

    tool_input: Dict[str, Any] = Field(..., description="Tool input parameters")
    auto_approve: bool = Field(False, description="Auto-approve execution")


# ==================== Tool Schemas ====================


class ToolParameterSchema(BaseModel):
    """Schema for a tool parameter"""

    type: str
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[str]] = None


class ToolInfo(BaseModel):
    """Information about a tool"""

    name: str
    description: str
    parameters: Dict[str, ToolParameterSchema]
    requires_approval: bool
    allowed_roles: List[str]
    category: str
    version: str = "1.0.0"


class ToolListResponse(BaseModel):
    """Response for list of tools"""

    tools: List[ToolInfo]
    total: int


# ==================== Audit & Timeline ====================


class TimelineEvent(BaseModel):
    """A single event in the task timeline"""

    timestamp: datetime
    event_type: str  # "thought", "tool_execution", "state_change"
    agent_name: Optional[str]
    description: str
    details: Optional[Dict[str, Any]]


class TaskTimelineResponse(BaseModel):
    """Response for task timeline"""

    task_id: UUID
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime]
    events: List[TimelineEvent]
    total_duration_ms: Optional[int]


# ==================== Classification ====================


class ClassificationResult(BaseModel):
    """Result from classifier agent"""

    task_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    tools_needed: List[str]
    reasoning: str
    priority_adjustment: Optional[int] = None
    escalation_required: bool = False
    escalation_reason: Optional[str] = None


# ==================== Agent Internal Schemas ====================


class AgentAction(BaseModel):
    """An action to be taken by an agent"""

    action: str
    action_input: Dict[str, Any]
    reasoning: Optional[str] = None


class AgentObservation(BaseModel):
    """Observation from an agent action"""

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class StateTransition(BaseModel):
    """A state transition in the task lifecycle"""

    from_state: str
    to_state: str
    timestamp: datetime
    reason: Optional[str] = None
    agent: Optional[str] = None
