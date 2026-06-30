"""State machine definitions for task lifecycle"""

from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime


class TaskState(str, Enum):
    """Task state enumeration for state machine"""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    EXECUTING = "executing"
    EXECUTED = "executed"
    ESCALATING = "escalating"
    ESCALATED = "escalated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TransitionTrigger(str, Enum):
    """Triggers for state transitions"""

    START_CLASSIFY = "start_classify"
    CLASSIFY_COMPLETE = "classify_complete"
    CLASSIFY_FAILED = "classify_failed"
    START_EXECUTE = "start_execute"
    EXECUTE_COMPLETE = "execute_complete"
    EXECUTE_FAILED = "execute_failed"
    ESCALATE = "escalate"
    ESCALATE_COMPLETE = "escalate_complete"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"
    RETRY = "retry"


@dataclass
class StateTransition:
    """Represents a state transition"""

    from_state: TaskState
    to_state: TaskState
    trigger: TransitionTrigger
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: Optional[str] = None
    agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Define valid state transitions
VALID_TRANSITIONS: Dict[TaskState, Dict[TransitionTrigger, TaskState]] = {
    TaskState.PENDING: {
        TransitionTrigger.START_CLASSIFY: TaskState.CLASSIFYING,
        TransitionTrigger.CANCEL: TaskState.CANCELLED,
    },
    TaskState.CLASSIFYING: {
        TransitionTrigger.CLASSIFY_COMPLETE: TaskState.CLASSIFIED,
        TransitionTrigger.CLASSIFY_FAILED: TaskState.FAILED,
        TransitionTrigger.ESCALATE: TaskState.ESCALATING,
        TransitionTrigger.CANCEL: TaskState.CANCELLED,
    },
    TaskState.CLASSIFIED: {
        TransitionTrigger.START_EXECUTE: TaskState.EXECUTING,
        TransitionTrigger.ESCALATE: TaskState.ESCALATING,
        TransitionTrigger.COMPLETE: TaskState.COMPLETED,
        TransitionTrigger.CANCEL: TaskState.CANCELLED,
    },
    TaskState.EXECUTING: {
        TransitionTrigger.EXECUTE_COMPLETE: TaskState.EXECUTED,
        TransitionTrigger.EXECUTE_FAILED: TaskState.FAILED,
        TransitionTrigger.ESCALATE: TaskState.ESCALATING,
        TransitionTrigger.RETRY: TaskState.RETRYING,
        TransitionTrigger.CANCEL: TaskState.CANCELLED,
    },
    TaskState.EXECUTED: {
        TransitionTrigger.COMPLETE: TaskState.COMPLETED,
        TransitionTrigger.ESCALATE: TaskState.ESCALATING,
    },
    TaskState.ESCALATING: {
        TransitionTrigger.ESCALATE_COMPLETE: TaskState.ESCALATED,
        TransitionTrigger.COMPLETE: TaskState.COMPLETED,
        TransitionTrigger.FAIL: TaskState.FAILED,
    },
    TaskState.ESCALATED: {
        TransitionTrigger.COMPLETE: TaskState.COMPLETED,
        TransitionTrigger.START_EXECUTE: TaskState.EXECUTING,
        TransitionTrigger.FAIL: TaskState.FAILED,
    },
    TaskState.FAILED: {
        TransitionTrigger.RETRY: TaskState.RETRYING,
        TransitionTrigger.COMPLETE: TaskState.COMPLETED,  # Manual resolution
    },
    TaskState.RETRYING: {
        TransitionTrigger.START_CLASSIFY: TaskState.CLASSIFYING,
        TransitionTrigger.START_EXECUTE: TaskState.EXECUTING,
        TransitionTrigger.FAIL: TaskState.FAILED,
    },
    TaskState.COMPLETED: {},  # Terminal state
    TaskState.CANCELLED: {},  # Terminal state
}


class StateMachine:
    """
    State machine for managing task lifecycle.

    Usage:
        sm = StateMachine(TaskState.PENDING)
        sm.transition(TransitionTrigger.START_CLASSIFY)
        assert sm.current_state == TaskState.CLASSIFYING
    """

    def __init__(self, initial_state: TaskState = TaskState.PENDING):
        self._current_state = initial_state
        self._history: List[StateTransition] = []

    @property
    def current_state(self) -> TaskState:
        """Get current state"""
        return self._current_state

    @property
    def history(self) -> List[StateTransition]:
        """Get state transition history"""
        return self._history.copy()

    def can_transition(self, trigger: TransitionTrigger) -> bool:
        """Check if transition is valid"""
        return trigger in VALID_TRANSITIONS.get(self._current_state, {})

    def transition(
        self,
        trigger: TransitionTrigger,
        reason: Optional[str] = None,
        agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskState:
        """
        Execute a state transition.

        Args:
            trigger: The transition trigger
            reason: Optional reason for the transition
            agent: Agent that initiated the transition
            metadata: Additional metadata

        Returns:
            The new state

        Raises:
            ValueError: If transition is not valid
        """
        if not self.can_transition(trigger):
            raise ValueError(
                f"Invalid transition: cannot {trigger.value} from {self._current_state.value}"
            )

        old_state = self._current_state
        new_state = VALID_TRANSITIONS[self._current_state][trigger]

        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            trigger=trigger,
            reason=reason,
            agent=agent,
            metadata=metadata or {},
        )

        self._history.append(transition)
        self._current_state = new_state

        return self._current_state

    def get_valid_triggers(self) -> List[TransitionTrigger]:
        """Get list of valid triggers from current state"""
        return list(VALID_TRANSITIONS.get(self._current_state, {}).keys())

    def is_terminal(self) -> bool:
        """Check if current state is terminal"""
        return self._current_state in (TaskState.COMPLETED, TaskState.CANCELLED)

    def reset(self) -> None:
        """Reset state machine to initial state"""
        self._current_state = TaskState.PENDING
        self._history.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state machine to dict"""
        return {
            "current_state": self._current_state.value,
            "history": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "trigger": t.trigger.value,
                    "timestamp": t.timestamp.isoformat(),
                    "reason": t.reason,
                    "agent": t.agent,
                    "metadata": t.metadata,
                }
                for t in self._history
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateMachine":
        """Deserialize state machine from dict"""
        sm = cls(TaskState(data["current_state"]))

        for t in data.get("history", []):
            transition = StateTransition(
                from_state=TaskState(t["from_state"]),
                to_state=TaskState(t["to_state"]),
                trigger=TransitionTrigger(t["trigger"]),
                timestamp=datetime.fromisoformat(t["timestamp"]),
                reason=t.get("reason"),
                agent=t.get("agent"),
                metadata=t.get("metadata", {}),
            )
            sm._history.append(transition)

        return sm
