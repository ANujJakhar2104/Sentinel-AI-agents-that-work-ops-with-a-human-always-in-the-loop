"""Escalator Agent for handling tasks requiring human intervention"""

from typing import Dict, Any, Optional
from uuid import UUID
import json

from langchain.schema import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.models.schemas import AgentAction, AgentObservation
from app.services.audit import AuditService


ESCALATION_PROMPT = """You are creating an escalation for human review.

Task Information:
- Task ID: {task_id}
- Classification: {classification}
- Reason for Escalation: {reason}

Context:
{context}

Create an escalation summary that includes:
1. Clear title describing the issue
2. Summary of what the task is about
3. Why it needs human attention
4. Suggested actions for the human operator
5. Risk level (low, medium, high)

Respond in JSON format:
{{
  "title": "Escalation title",
  "summary": "Brief summary of the issue",
  "reason": "Why human attention is needed",
  "suggested_actions": ["action1", "action2"],
  "risk_level": "medium",
  "context_summary": "Key context for the operator"
}}

JSON Response:"""


class EscalatorAgent(BaseAgent):
    """
    Agent responsible for escalating tasks to human operators.

    Responsibilities:
    - Create clear escalation summaries
    - Provide context for human reviewers
    - Suggest potential actions
    - Assess risk level
    """

    name = "escalator"
    description = "Handles escalation of tasks requiring human intervention"
    version = "1.0.0"

    def __init__(
        self, task_id: UUID, audit_service: Optional[AuditService] = None, **kwargs
    ):
        super().__init__(task_id, audit_service=audit_service, **kwargs)

    @property
    def system_prompt(self) -> str:
        return """You are an escalation agent. Create clear, concise escalations for human operators.
Include all relevant context and suggest actions. Be professional and thorough."""

    async def think(self, context: Dict[str, Any]) -> AgentAction:
        """Generate escalation summary using LLM"""
        reason = context.get("reason", "Unspecified reason")
        classification = context.get("classification", {})

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(
                content=ESCALATION_PROMPT.format(
                    task_id=str(self.task_id),
                    classification=json.dumps(classification, default=str),
                    reason=reason,
                    context=json.dumps(context, default=str),
                )
            ),
        ]

        response = await self.call_llm(messages)

        escalation = self._parse_escalation(response)

        return AgentAction(
            action="create_escalation",
            action_input=escalation,
            reasoning=f"Creating escalation: {escalation.get('title', 'Unknown')}",
        )

    async def act(self, action: AgentAction) -> AgentObservation:
        """Create the escalation"""
        if action.action == "create_escalation":
            # Here you would integrate with ticketing/notification systems
            # For now, we just log and return the escalation

            escalation_data = action.action_input
            escalation_data["task_id"] = str(self.task_id)
            escalation_data["status"] = "open"
            escalation_data["created_at"] = str(
                action.action_input.get("created_at", "now")
            )

            return AgentObservation(success=True, result=escalation_data)

        return AgentObservation(success=False, error=f"Unknown action: {action.action}")

    def _parse_escalation(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into escalation dict"""
        response = response.strip()

        # Remove markdown if present
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            import re

            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    data = {}
            else:
                data = {}

        return {
            "title": data.get("title", "Manual Review Required"),
            "summary": data.get("summary", ""),
            "reason": data.get("reason", ""),
            "suggested_actions": data.get("suggested_actions", []),
            "risk_level": data.get("risk_level", "medium"),
            "context_summary": data.get("context_summary", ""),
        }

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run escalation and return result"""
        action = await self.think(context)
        observation = await self.act(action)

        if observation.success:
            return observation.result
        else:
            return {
                "status": "error",
                "error": observation.error,
                "task_id": str(self.task_id),
            }
