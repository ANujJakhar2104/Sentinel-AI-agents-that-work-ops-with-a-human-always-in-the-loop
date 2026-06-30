"""Central Orchestrator Agent that manages the task lifecycle"""

from typing import Dict, Any, Optional
from uuid import UUID
import logging

from app.agents.base import BaseAgent
from app.agents.state_machine import StateMachine, TaskState, TransitionTrigger
from app.agents.classifier import ClassifierAgent
from app.agents.tool_runner import ToolRunnerAgent
from app.agents.escalator import EscalatorAgent
from app.models.schemas import AgentAction, AgentObservation, ClassificationResult
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Central orchestrator that coordinates specialized agents.

    Responsibilities:
    - Manage task lifecycle using state machine
    - Route tasks to appropriate specialized agents
    - Handle state transitions
    - Implement retry logic
    - Coordinate between agents
    """

    name = "orchestrator"
    description = (
        "Central orchestrator that manages task execution across specialized agents"
    )
    version = "1.0.0"

    def __init__(
        self, task_id: UUID, audit_service: Optional[AuditService] = None, **kwargs
    ):
        super().__init__(task_id, audit_service=audit_service, **kwargs)

        self.state_machine = StateMachine(TaskState.PENDING)
        self.classifier = None
        self.tool_runner = None
        self.escalator = None
        self._classification_result: Optional[ClassificationResult] = None
        self._execution_results: list = []

    @property
    def system_prompt(self) -> str:
        return """You are the Orchestrator agent responsible for managing task execution.

Your role is to:
1. Coordinate between specialized agents (Classifier, ToolRunner, Escalator)
2. Manage the task lifecycle state machine
3. Handle errors and implement retry logic
4. Ensure audit compliance

Always think through the current state and determine the next action.
Respond with clear reasoning about what needs to happen next."""

    async def think(self, context: Dict[str, Any]) -> AgentAction:
        """Determine next action based on current state and context"""
        current_state = self.state_machine.current_state

        # Determine action based on state
        if current_state == TaskState.PENDING:
            return AgentAction(
                action="classify",
                action_input={"context": context},
                reasoning="Task is pending, need to classify it first",
            )

        elif current_state == TaskState.CLASSIFIED:
            classification = context.get("classification")
            if classification and classification.get("escalation_required"):
                return AgentAction(
                    action="escalate",
                    action_input={
                        "reason": classification.get("escalation_reason"),
                        "classification": classification,
                    },
                    reasoning="Classification indicates escalation is required",
                )
            return AgentAction(
                action="execute",
                action_input={
                    "tools": classification.get("tools_needed", []),
                    "classification": classification,
                },
                reasoning="Proceeding to execute required tools",
            )

        elif current_state == TaskState.EXECUTED:
            return AgentAction(
                action="finish",
                action_input={
                    "status": "completed",
                    "results": context.get("execution_results", []),
                },
                reasoning="All tools executed, task is complete",
            )

        elif current_state == TaskState.ESCALATED:
            return AgentAction(
                action="finish",
                action_input={
                    "status": "escalated",
                    "escalation": context.get("escalation"),
                },
                reasoning="Task has been escalated to human review",
            )

        elif current_state == TaskState.FAILED:
            retry_count = context.get("retry_count", 0)
            max_retries = context.get("max_retries", 3)

            if retry_count < max_retries:
                return AgentAction(
                    action="retry",
                    action_input={"retry_count": retry_count + 1},
                    reasoning=f"Task failed, retrying ({retry_count + 1}/{max_retries})",
                )
            return AgentAction(
                action="finish",
                action_input={
                    "status": "failed",
                    "error": context.get("error"),
                    "retry_count": retry_count,
                },
                reasoning="Task failed and max retries exceeded",
            )

        # Default: finish with current state
        return AgentAction(
            action="finish",
            action_input={"status": current_state.value, "context": context},
            reasoning=f"Reached state {current_state.value}, finishing",
        )

    async def act(self, action: AgentAction) -> AgentObservation:
        """Execute the determined action"""
        action_type = action.action

        try:
            if action_type == "classify":
                return await self._do_classify(action.action_input)
            elif action_type == "execute":
                return await self._do_execute(action.action_input)
            elif action_type == "escalate":
                return await self._do_escalate(action.action_input)
            elif action_type == "retry":
                return await self._do_retry(action.action_input)
            elif action_type == "finish":
                return AgentObservation(success=True, result=action.action_input)
            else:
                return AgentObservation(
                    success=False, error=f"Unknown action: {action_type}"
                )
        except Exception as e:
            logger.error(f"Orchestrator action failed: {e}")
            return AgentObservation(success=False, error=str(e))

    async def _do_classify(self, action_input: Dict[str, Any]) -> AgentObservation:
        """Classify the task using ClassifierAgent"""
        # Transition state
        self.state_machine.transition(TransitionTrigger.START_CLASSIFY, agent=self.name)

        # Create and run classifier
        self.classifier = ClassifierAgent(
            task_id=self.task_id, audit_service=self.audit_service
        )

        result = await self.classifier.run(action_input.get("context", {}))

        if result.get("status") == "error":
            self.state_machine.transition(
                TransitionTrigger.CLASSIFY_FAILED,
                reason=result.get("error"),
                agent=self.name,
            )
            return AgentObservation(
                success=False, error=result.get("error"), result=result
            )

        # Store classification result
        self._classification_result = ClassificationResult(
            task_type=result.get("task_type", "unknown"),
            confidence=result.get("confidence", 0.0),
            tools_needed=result.get("tools_needed", []),
            reasoning=result.get("reasoning", ""),
            escalation_required=result.get("escalation_required", False),
            escalation_reason=result.get("escalation_reason"),
        )

        # Transition state
        self.state_machine.transition(
            TransitionTrigger.CLASSIFY_COMPLETE, agent=self.name
        )

        return AgentObservation(
            success=True,
            result={"classification": self._classification_result.model_dump()},
        )

    async def _do_execute(self, action_input: Dict[str, Any]) -> AgentObservation:
        """Execute tools using ToolRunnerAgent"""
        # Transition state
        self.state_machine.transition(TransitionTrigger.START_EXECUTE, agent=self.name)

        # Create and run tool runner
        self.tool_runner = ToolRunnerAgent(
            task_id=self.task_id, audit_service=self.audit_service
        )

        classification = action_input.get("classification", {})
        tools = classification.get("tools_needed", [])

        result = await self.tool_runner.run(
            {"tools": tools, "context": action_input.get("context", {})}
        )

        if result.get("status") == "error":
            self.state_machine.transition(
                TransitionTrigger.EXECUTE_FAILED,
                reason=result.get("error"),
                agent=self.name,
            )
            return AgentObservation(
                success=False, error=result.get("error"), result=result
            )

        # Store execution results
        self._execution_results = result.get("results", [])

        # Transition state
        self.state_machine.transition(
            TransitionTrigger.EXECUTE_COMPLETE, agent=self.name
        )

        return AgentObservation(
            success=True, result={"execution_results": self._execution_results}
        )

    async def _do_escalate(self, action_input: Dict[str, Any]) -> AgentObservation:
        """Escalate task using EscalatorAgent"""
        # Transition state
        self.state_machine.transition(
            TransitionTrigger.ESCALATE,
            reason=action_input.get("reason"),
            agent=self.name,
        )

        # Create and run escalator
        self.escalator = EscalatorAgent(
            task_id=self.task_id, audit_service=self.audit_service
        )

        result = await self.escalator.run(
            {
                "reason": action_input.get("reason"),
                "classification": action_input.get("classification"),
            }
        )

        # Transition state
        self.state_machine.transition(
            TransitionTrigger.ESCALATE_COMPLETE, agent=self.name
        )

        return AgentObservation(success=True, result={"escalation": result})

    async def _do_retry(self, action_input: Dict[str, Any]) -> AgentObservation:
        """Handle retry logic"""
        self.state_machine.transition(
            TransitionTrigger.RETRY,
            reason=f"Retry attempt {action_input.get('retry_count')}",
            agent=self.name,
        )

        # Reset and restart classification
        return AgentObservation(
            success=True,
            result={"retry": True, "retry_count": action_input.get("retry_count")},
        )

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run the orchestrator loop"""
        # Initialize state machine from task if available
        if "state_history" in context:
            self.state_machine = StateMachine.from_dict(
                {
                    "current_state": context.get("current_state", "pending"),
                    "history": context.get("state_history", []),
                }
            )

        # Run the base agent loop
        result = await super().run(context)

        # Add state machine info to result
        result["state_machine"] = self.state_machine.to_dict()

        return result

    def get_state_machine(self) -> StateMachine:
        """Get the state machine instance"""
        return self.state_machine
