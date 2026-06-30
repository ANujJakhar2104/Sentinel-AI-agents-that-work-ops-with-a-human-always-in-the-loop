"""Tests for agent functionality"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from app.agents.state_machine import StateMachine, TaskState, TransitionTrigger
from app.agents.base import BaseAgent
from app.models.schemas import AgentAction, AgentObservation


class TestStateMachine:
    """Tests for the state machine"""

    def test_initial_state(self):
        """Test initial state is PENDING"""
        sm = StateMachine()
        assert sm.current_state == TaskState.PENDING

    def test_valid_transition(self):
        """Test a valid state transition"""
        sm = StateMachine()
        new_state = sm.transition(TransitionTrigger.START_CLASSIFY)
        assert new_state == TaskState.CLASSIFYING
        assert sm.current_state == TaskState.CLASSIFYING

    def test_invalid_transition(self):
        """Test an invalid state transition raises error"""
        sm = StateMachine()
        # Cannot go from PENDING to COMPLETED directly
        with pytest.raises(ValueError):
            sm.transition(TransitionTrigger.COMPLETE)

    def test_history_tracking(self):
        """Test that state transitions are tracked in history"""
        sm = StateMachine()
        sm.transition(TransitionTrigger.START_CLASSIFY)
        sm.transition(TransitionTrigger.CLASSIFY_COMPLETE)

        assert len(sm.history) == 2
        assert sm.history[0].from_state == TaskState.PENDING
        assert sm.history[1].to_state == TaskState.CLASSIFIED

    def test_terminal_state_detection(self):
        """Test terminal state detection"""
        sm = StateMachine()
        assert not sm.is_terminal()

        # Transition to COMPLETED
        sm._current_state = TaskState.COMPLETED
        assert sm.is_terminal()

    def test_valid_triggers(self):
        """Test getting valid triggers from a state"""
        sm = StateMachine()
        triggers = sm.get_valid_triggers()

        assert TransitionTrigger.START_CLASSIFY in triggers
        assert TransitionTrigger.CANCEL in triggers
        assert TransitionTrigger.COMPLETE not in triggers

    def test_serialization(self):
        """Test state machine serialization"""
        sm = StateMachine()
        sm.transition(TransitionTrigger.START_CLASSIFY)

        data = sm.to_dict()
        assert data["current_state"] == "classifying"
        assert len(data["history"]) == 1

        # Deserialize
        sm2 = StateMachine.from_dict(data)
        assert sm2.current_state == TaskState.CLASSIFYING
        assert len(sm2.history) == 1


class ConcreteTestAgent(BaseAgent):
    """Concrete agent for testing"""

    name = "test_agent"
    description = "Test agent"

    async def think(self, context):
        return AgentAction(action="test", action_input={}, reasoning="test")

    async def act(self, action):
        return AgentObservation(success=True, result={"status": "ok"})


class TestBaseAgent:
    """Tests for the base agent class"""

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent can be initialized"""
        task_id = uuid4()
        agent = ConcreteTestAgent(task_id=task_id, api_key="test-key")

        assert agent.task_id == task_id
        assert agent.name == "test_agent"

    @pytest.mark.asyncio
    async def test_agent_without_api_key(self):
        """Test agent fails without API key"""
        task_id = uuid4()

        with pytest.raises(ValueError, match="API key"):
            ConcreteTestAgent(task_id=task_id, api_key=None)

    @pytest.mark.asyncio
    async def test_thought_logging(self):
        """Test thoughts are logged"""
        task_id = uuid4()
        agent = ConcreteTestAgent(task_id=task_id, api_key="test-key")

        await agent.log_thought(
            thought="Test thought",
            action="test",
            action_input={"key": "value"},
            observation="Test observation",
        )

        assert len(agent.get_thoughts()) == 1
        thought = agent.get_thoughts()[0]
        assert thought["thought"] == "Test thought"

    @pytest.mark.asyncio
    async def test_agent_run(self):
        """Test agent run loop"""
        task_id = uuid4()
        agent = ConcreteTestAgent(task_id=task_id, api_key="test-key")
        agent._max_iterations = 1  # Limit iterations for test

        # Mock the finish action
        async def mock_think(context):
            return AgentAction(
                action="finish", action_input={"result": "done"}, reasoning="complete"
            )

        agent.think = mock_think

        result = await agent.run({})

        assert "status" in result or "result" in result


class TestAgentAction:
    """Tests for AgentAction schema"""

    def test_action_creation(self):
        """Test creating an agent action"""
        action = AgentAction(
            action="test_action",
            action_input={"key": "value"},
            reasoning="Test reasoning",
        )

        assert action.action == "test_action"
        assert action.action_input == {"key": "value"}
        assert action.reasoning == "Test reasoning"


class TestAgentObservation:
    """Tests for AgentObservation schema"""

    def test_success_observation(self):
        """Test creating a successful observation"""
        obs = AgentObservation(success=True, result={"data": "value"})

        assert obs.success is True
        assert obs.result == {"data": "value"}
        assert obs.error is None

    def test_failure_observation(self):
        """Test creating a failure observation"""
        obs = AgentObservation(success=False, error="Something went wrong")

        assert obs.success is False
        assert obs.error == "Something went wrong"
