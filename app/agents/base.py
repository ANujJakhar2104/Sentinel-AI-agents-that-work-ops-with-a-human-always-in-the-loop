"""Base agent class with ReAct pattern implementation"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
import time

from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatOpenAI

from app.config import get_settings
from app.models.schemas import AgentAction, AgentObservation
from app.services.audit import AuditService

settings = get_settings()


class BaseAgent(ABC):
    """
    Base class for all agents implementing the ReAct pattern.

    The ReAct (Reasoning + Acting) pattern:
    1. Thought: Agent reasons about the current situation
    2. Action: Agent decides on an action to take
    3. Observation: Agent observes the result of the action
    4. Repeat until task is complete

    Every step is logged for audit trail.
    """

    name: str = "base_agent"
    description: str = "Base agent class"
    version: str = "1.0.0"

    def __init__(
        self,
        task_id: UUID,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        audit_service: Optional[AuditService] = None,
    ):
        """
        Initialize the agent.

        Args:
            task_id: The task ID this agent is working on
            api_key: OpenAI API key (defaults to settings)
            model: LLM model to use (defaults to settings)
            audit_service: Service for logging thoughts/actions
        """
        self.task_id = task_id
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.llm_model
        self.audit_service = audit_service

        if not self.api_key:
            raise ValueError(f"OpenAI API key is required for {self.name}")

        self._llm = None
        self._max_iterations = 10
        self._thoughts: List[Dict[str, Any]] = []

    @property
    def llm(self):
        """Lazy-load LLM instance"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.model,
                temperature=0,
                api_key=self.api_key,
            )
        return self._llm

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for this agent"""
        return f"You are {self.name}. {self.description}"

    @abstractmethod
    async def think(self, context: Dict[str, Any]) -> AgentAction:
        """
        Generate the next thought and action.

        Args:
            context: Current context including input, history, etc.

        Returns:
            The action to take
        """
        pass

    @abstractmethod
    async def act(self, action: AgentAction) -> AgentObservation:
        """
        Execute an action.

        Args:
            action: The action to execute

        Returns:
            The observation from the action
        """
        pass

    async def log_thought(
        self,
        thought: Optional[str],
        action: Optional[str],
        action_input: Optional[Dict[str, Any]],
        observation: Optional[str],
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        """
        Log a thought-action-observation to the audit trail.

        Args:
            thought: Agent's reasoning
            action: Action taken
            action_input: Input to the action
            observation: Result of the action
            tokens_used: Number of tokens used
            latency_ms: Time taken in milliseconds
        """
        thought_record = {
            "thought": thought,
            "action": action,
            "action_input": action_input,
            "observation": observation,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "created_at": datetime.utcnow(),
        }
        self._thoughts.append(thought_record)

        # Log to audit service if available
        if self.audit_service:
            await self.audit_service.log_thought(
                task_id=self.task_id,
                agent_name=self.name,
                agent_version=self.version,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                model=self.model,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
            )

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the agent's main loop.

        Args:
            context: Initial context for the agent

        Returns:
            Final result from the agent
        """
        iterations = 0
        current_context = context.copy()

        while iterations < self._max_iterations:
            iterations += 1

            # Think
            start_time = time.time()
            action = await self.think(current_context)
            latency_ms = int((time.time() - start_time) * 1000)

            # Check if we should finish
            if action.action == "finish":
                await self.log_thought(
                    thought=action.reasoning,
                    action="finish",
                    action_input=action.action_input,
                    observation="Task completed",
                    latency_ms=latency_ms,
                )
                return action.action_input

            # Act
            start_time = time.time()
            observation = await self.act(action)
            latency_ms = int((time.time() - start_time) * 1000)

            # Log
            await self.log_thought(
                thought=action.reasoning,
                action=action.action,
                action_input=action.action_input,
                observation=observation.result
                if observation.success
                else observation.error,
                latency_ms=latency_ms,
            )

            # Update context
            current_context["last_action"] = action.action
            current_context["last_observation"] = (
                observation.result if observation.success else observation.error
            )
            current_context["iterations"] = iterations

            # Check for failure
            if not observation.success:
                # Could escalate or retry here
                current_context["errors"] = current_context.get("errors", [])
                current_context["errors"].append(observation.error)

        # Max iterations reached
        return {
            "status": "max_iterations_reached",
            "iterations": iterations,
            "last_context": current_context,
        }

    def get_thoughts(self) -> List[Dict[str, Any]]:
        """Get all logged thoughts"""
        return self._thoughts.copy()

    async def call_llm(self, messages: List) -> str:
        """
        Call the LLM with messages.

        Args:
            messages: List of messages (SystemMessage, HumanMessage, etc.)

        Returns:
            LLM response content
        """
        response = await self.llm.ainvoke(messages)
        return response.content
