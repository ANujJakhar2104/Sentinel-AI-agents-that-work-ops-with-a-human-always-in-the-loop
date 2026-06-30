"""Classifier Agent for analyzing and classifying tasks"""

from typing import Dict, Any, Optional, List
from uuid import UUID
import json
import re

from langchain.schema import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.models.schemas import AgentAction, AgentObservation, ClassificationResult
from app.services.audit import AuditService
from app.tools.registry import ToolRegistry


CLASSIFIER_PROMPT = """You are a classification agent. Analyze the incoming request and classify it.

Your task is to:
1. Determine the type of request (refund_request, account_issue, technical_support, billing_inquiry, etc.)
2. Identify what tools are needed to resolve this request
3. Assess confidence level (0.0-1.0)
4. Determine if escalation to a human is needed

Available tools:
{tools_description}

Request to classify:
{request}

Context:
{context}

Respond in JSON format:
{{
  "task_type": "type_of_request",
  "confidence": 0.95,
  "tools_needed": ["tool1", "tool2"],
  "reasoning": "explanation of classification",
  "escalation_required": false,
  "escalation_reason": "reason if escalation needed"
}}

JSON Response:"""


class ClassifierAgent(BaseAgent):
    """
    Agent responsible for classifying incoming requests.

    Responsibilities:
    - Analyze request content and context
    - Determine task type
    - Identify required tools
    - Assess confidence
    - Flag for escalation if needed
    """

    name = "classifier"
    description = "Classifies incoming requests and determines required actions"
    version = "1.0.0"

    def __init__(
        self, task_id: UUID, audit_service: Optional[AuditService] = None, **kwargs
    ):
        super().__init__(task_id, audit_service=audit_service, **kwargs)
        self._tools_description = self._build_tools_description()

    def _build_tools_description(self) -> str:
        """Build description of available tools"""
        tools = ToolRegistry.list_tools()
        descriptions = []
        for tool in tools:
            descriptions.append(f"- {tool['name']}: {tool['description']}")
        return "\n".join(descriptions) if descriptions else "No tools available"

    @property
    def system_prompt(self) -> str:
        return """You are a classification agent. Analyze requests and classify them accurately.
Determine the task type, required tools, confidence level, and whether escalation is needed.
Always respond with valid JSON."""

    async def think(self, context: Dict[str, Any]) -> AgentAction:
        """Generate classification using LLM"""
        request = context.get("input", {})
        request_text = request.get("request", str(request))

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(
                content=CLASSIFIER_PROMPT.format(
                    tools_description=self._tools_description,
                    request=request_text,
                    context=json.dumps(context, default=str),
                )
            ),
        ]

        response = await self.call_llm(messages)

        # Parse response
        classification = self._parse_classification(response)

        return AgentAction(
            action="classify",
            action_input=classification,
            reasoning=classification.get("reasoning", ""),
        )

    async def act(self, action: AgentAction) -> AgentObservation:
        """Store and return classification result"""
        if action.action == "classify":
            return AgentObservation(success=True, result=action.action_input)

        return AgentObservation(success=False, error=f"Unknown action: {action.action}")

    def _parse_classification(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into classification dict"""
        # Clean up response
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
            # Try to extract JSON
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    data = self._default_classification()
            else:
                data = self._default_classification()

        # Validate and normalize
        return {
            "task_type": data.get("task_type", "unknown"),
            "confidence": min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
            "tools_needed": data.get("tools_needed", []),
            "reasoning": data.get("reasoning", ""),
            "escalation_required": bool(data.get("escalation_required", False)),
            "escalation_reason": data.get("escalation_reason"),
        }

    def _default_classification(self) -> Dict[str, Any]:
        """Return default classification when parsing fails"""
        return {
            "task_type": "unknown",
            "confidence": 0.0,
            "tools_needed": [],
            "reasoning": "Failed to parse classification from LLM response",
            "escalation_required": True,
            "escalation_reason": "Could not classify request automatically",
        }

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run classification and return result"""
        # Execute think -> act cycle
        action = await self.think(context)
        observation = await self.act(action)

        if observation.success:
            return observation.result
        else:
            return {"status": "error", "error": observation.error}
