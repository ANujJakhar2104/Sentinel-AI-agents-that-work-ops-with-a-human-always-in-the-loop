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
            action_input={
                "tools": tools,
                "tool_info": tool_info,
                # YAHAN FIX HAI: Orchestrator se aaya hua context aage forward karo
                "context": context.get("context", context)
            },
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
        logger.info(f"Executing tool: {tool_name}")

        tool = ToolRegistry.get_tool(tool_name)
        if not tool:
            return {"tool": tool_name, "success": False, "error": f"Tool not found: {tool_name}"}

        try:
            # 1. Check exactly what input is being generated
            tool_input = self._prepare_tool_input(tool, context)
            logger.info(f"[{tool_name}] Prepared input: {tool_input}")

            # 2. Check if validation is failing silently
            validation = tool.validate_input(tool_input)
            if not validation.valid:
                error_msg = str(getattr(validation, 'errors', 'Validation failed (no exact error provided)'))
                logger.warning(f"[{tool_name}] Validation failed: {error_msg}")
                return {
                    "tool": tool_name,
                    "success": False,
                    "error": error_msg
                }

            execution_id = await self._log_execution_start(tool_name, tool_input)

            # 3. Execute tool
            logger.info(f"[{tool_name}] Starting execution...")
            result = await tool.execute(**tool_input)
            logger.info(f"[{tool_name}] Execution successful: {result}")

            await self._log_execution_complete(execution_id, result)
            return {"tool": tool_name, "success": True, "result": result}
            
        except Exception as e:
            # exc_info=True se pura stack trace (line number ke sath) print hoga
            logger.error(f"[{tool_name}] Tool execution crashed: {str(e)}", exc_info=True)
            return {"tool": tool_name, "success": False, "error": str(e)}

    def _prepare_tool_input(self, tool, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare input for a tool from context"""
        # Input may be at top level or nested under context.input
        input_data = context.get("input", {})
        if not input_data:
            input_data = context.get("context", {}).get("input", {})
            
        # 1. Start by copying ALL input data directly so we don't lose anything
        tool_input = dict(input_data)

        # 2. Map context to tool parameters safely
        schema_props = {}
        if hasattr(tool, "input_schema") and isinstance(tool.input_schema, dict):
            schema_props = tool.input_schema.get("properties", {})

        for param_name, param_spec in schema_props.items():
            if param_name in input_data:
                tool_input[param_name] = input_data[param_name]
            elif param_name == "user_id" and "user_id" in context:
                tool_input[param_name] = context["user_id"]
            elif param_name == "order_id" and "order_id" in input_data:
                tool_input[param_name] = input_data["order_id"]
            
        # 3. Auto-fill common fields for send_email if missing
        if hasattr(tool, 'name') and tool.name == "send_email":
            if "subject" not in tool_input:
                tool_input["subject"] = "Update on your request"
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
            try:
                await self.audit_service.log_tool_execution(
                    task_id=self.task_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    execution_id=execution_id,
                    status=ToolExecutionStatus.EXECUTING,
                )
            except Exception as e:
                logger.warning(f"Failed to log execution start: {e}")

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
            try:
                await self.audit_service.log_tool_execution(
                    task_id=self.task_id,
                    tool_name="unknown",
                    tool_input={},
                    execution_id=execution_id,
                    tool_output=result,
                    status=status,
                    error=error,
                )
            except Exception as e:
                logger.warning(f"Failed to log execution complete: {e}")

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
