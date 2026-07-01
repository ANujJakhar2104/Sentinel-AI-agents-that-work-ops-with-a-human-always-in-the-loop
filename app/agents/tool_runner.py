"""ToolRunner Agent for executing approved tools"""

from typing import Dict, Any, Optional, List
from uuid import UUID
import logging

from app.agents.base import BaseAgent
from app.models.schemas import AgentAction, AgentObservation
from app.services.audit import AuditService
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolRunnerAgent(BaseAgent):
    """
    Agent responsible for executing tools safely.

    Responsibilities:
    - Execute approved tools
    - Validate tool inputs
    - Handle tool execution errors
    - Log all executions for audit
    """

    name = "tool_runner"
    description = "Executes approved tools with safety checks and audit logging"
    version = "1.0.0"

    def __init__(
        self, task_id: UUID, audit_service: Optional[AuditService] = None, **kwargs
    ):
        super().__init__(task_id, audit_service=audit_service, **kwargs)
        self._execution_results: List[Dict[str, Any]] = []

    @property
    def system_prompt(self) -> str:
        return """You are a tool runner agent. Execute approved tools and report results.
Validate inputs before execution and handle errors gracefully.
Always log execution details for audit compliance."""

    async def think(self, context: Dict[str, Any]) -> AgentAction:
        """Determine which tools to execute"""
        tools = context.get("tools", [])

        if not tools:
            return AgentAction(
                action="finish",
                action_input={"status": "completed", "results": []},
                reasoning="No tools to execute",
            )

        # Get tool details
        tool_info = []
        for tool_name in tools:
            info = ToolRegistry.get_tool_info(tool_name)
            if info:
                tool_info.append(info)

        return AgentAction(
            action="execute_tools",
            action_input={"tools": tools, "tool_info": tool_info},
            reasoning=f"Executing {len(tools)} tools: {', '.join(tools)}",
        )

    async def act(self, action: AgentAction) -> AgentObservation:
        """Execute the tools"""
        if action.action == "finish":
            return AgentObservation(success=True, result=action.action_input)

        if action.action == "execute_tools":
            return await self._execute_tools(action.action_input)

        return AgentObservation(success=False, error=f"Unknown action: {action.action}")

    async def _execute_tools(self, action_input: Dict[str, Any]) -> AgentObservation:
        """Execute a list of tools"""
        tools = action_input.get("tools", [])
        results = []

        for tool_name in tools:
            result = await self._execute_single_tool(
                tool_name, action_input.get("context", {})
            )
            results.append(result)

            # Stop on critical failure
            if not result.get("success") and result.get("critical", False):
                break

        self._execution_results = results

        # Check overall success
        all_success = all(r.get("success", False) for r in results)

        return AgentObservation(
            success=all_success,
            result={
                "results": results,
                "status": "completed" if all_success else "partial_failure",
            },
        )

    async def _execute_single_tool(
        self, tool_name: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single tool with error handling"""
        logger.info(f"Executing tool: {tool_name}")

        # Get tool from registry
        tool = ToolRegistry.get_tool(tool_name)
        if not tool:
            return {
                "tool": tool_name,
                "success": False,
                "error": f"Tool not found: {tool_name}",
            }

        # Prepare input from context
        tool_input = self._prepare_tool_input(tool, context)

        # Validate input
        validation = tool.validate_input(tool_input)
        if not validation.valid:
            return {
                "tool": tool_name,
                "success": False,
                "error": f"Invalid input: {validation.error}",
            }

        # Log tool execution start
        execution_id = await self._log_execution_start(tool_name, tool_input)

        try:
            # Execute tool
            result = await tool.execute(**tool_input)

            # Log success
            await self._log_execution_complete(execution_id, result)

            return {"tool": tool_name, "success": True, "result": result}
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")

            # Log failure
            await self._log_execution_complete(execution_id, None, str(e))

            return {
                "tool": tool_name,
                "success": False,
                "error": str(e),
                "critical": tool.critical_on_failure,
            }

    def _prepare_tool_input(self, tool, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare input for a tool from context"""
        # Input may be at top level or nested under context.input
        input_data = context.get("input", {})
        if not input_data:
            input_data = context.get("context", {}).get("input", {})
        tool_input = {}

        # Map context to tool parameters
        for param_name, param_spec in tool.input_schema.get("properties", {}).items():
            # Try to get from input first
            if param_name in input_data:
                tool_input[param_name] = input_data[param_name]
            # Try common variations
            elif param_name == "user_id" and "user_id" in context:
                tool_input[param_name] = context["user_id"]
            elif param_name == "order_id" and "order_id" in input_data:
                tool_input[param_name] = input_data["order_id"]
            
        # Auto-fill common fields for send_email if missing
        if hasattr(tool, 'name') and tool.name == "send_email":
            if "subject" not in tool_input:
                tool_input["subject"] = f"Update on your request"
            if "body" not in tool_input:
                tool_input["body"] = f"Your request has been processed. Order: {input_data.get('order_id', 'N/A')}. Amount: {input_data.get('amount', 'N/A')}."
            if "user_id" not in tool_input:
                tool_input["user_id"] = input_data.get("user_id", input_data.get("order_id", "unknown"))

        return tool_input


    async def _log_execution_start(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> UUID:
        """Log the start of tool execution"""
        from app.models.db_models import ToolExecutionStatus
        from uuid import uuid4

        execution_id = uuid4()

        if self.audit_service:
            await self.audit_service.log_tool_execution(
                task_id=self.task_id,
                tool_name=tool_name,
                tool_input=tool_input,
                execution_id=execution_id,
                status=ToolExecutionStatus.EXECUTING,
            )

        return execution_id

    async def _log_execution_complete(
        self,
        execution_id: UUID,
        result: Optional[Dict[str, Any]],
        error: Optional[str] = None,
    ):
        """Log the completion of tool execution"""
        from app.models.db_models import ToolExecutionStatus

        status = (
            ToolExecutionStatus.COMPLETED if not error else ToolExecutionStatus.FAILED
        )

        if self.audit_service:
            await self.audit_service.log_tool_execution(
                execution_id=execution_id,
                task_id=self.task_id,
                tool_output=result,
                status=status,
                error=error,
            )

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run tool execution and return results"""
        action = await self.think(context)
        observation = await self.act(action)

        if observation.success:
            return observation.result
        else:
            return {
                "status": "error",
                "error": observation.error,
                "partial_results": self._execution_results,
            }
