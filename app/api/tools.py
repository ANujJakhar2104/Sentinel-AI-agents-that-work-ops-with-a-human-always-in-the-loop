"""Tool management API endpoints"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import (
    ToolListResponse,
    ToolInfo,
    ToolExecuteRequest,
    ToolExecutionResponse,
)
from app.tools.registry import ToolRegistry, register_all_tools

router = APIRouter(prefix="/api/tools", tags=["Tools"])

# Register tools on module load
register_all_tools()


@router.get("", response_model=ToolListResponse, summary="List available tools")
async def list_tools() -> ToolListResponse:
    """
    List all available tools that agents can use.
    """
    tools = ToolRegistry.list_tools()

    tool_infos = [
        ToolInfo(
            name=t["name"],
            description=t["description"],
            parameters={
                k: {
                    "type": v.get("type", "any"),
                    "description": v.get("description", ""),
                }
                for k, v in t.get("input_schema", {}).get("properties", {}).items()
            },
            requires_approval=t["requires_approval"],
            allowed_roles=t["allowed_roles"],
            category=t["category"],
            version=t["version"],
        )
        for t in tools
    ]

    return ToolListResponse(tools=tool_infos, total=len(tool_infos))


@router.get("/{tool_name}", response_model=ToolInfo, summary="Get tool details")
async def get_tool(tool_name: str) -> ToolInfo:
    """
    Get details of a specific tool.
    """
    tool_info = ToolRegistry.get_tool_info(tool_name)

    if not tool_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
        )

    return ToolInfo(
        name=tool_info["name"],
        description=tool_info["description"],
        parameters={
            k: {"type": v.get("type", "any"), "description": v.get("description", "")}
            for k, v in tool_info.get("input_schema", {}).get("properties", {}).items()
        },
        requires_approval=tool_info["requires_approval"],
        allowed_roles=tool_info["allowed_roles"],
        category=tool_info["category"],
        version=tool_info["version"],
    )


@router.post(
    "/{tool_name}/execute",
    response_model=ToolExecutionResponse,
    summary="Execute a tool directly",
)
async def execute_tool(
    tool_name: str, request: ToolExecuteRequest, db=Depends(lambda: None)
) -> ToolExecutionResponse:
    """
    Execute a tool directly (for testing or manual operations).

    Note: In production, most tools should only be executed by agents
    through the proper workflow to ensure audit compliance.
    """
    from uuid import uuid4
    from datetime import datetime
    from app.models.schemas import ToolExecutionStatus

    tool = ToolRegistry.get_tool(tool_name)

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
        )

    # Validate input
    validation = tool.validate_input(request.tool_input)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {validation.error}",
        )

    # Execute
    try:
        result = await tool.execute(**request.tool_input)

        return ToolExecutionResponse(
            id=uuid4(),
            task_id=uuid4(),  # No associated task
            thought_id=None,
            tool_name=tool_name,
            tool_input=request.tool_input,
            tool_output=result,
            status=ToolExecutionStatus.COMPLETED,
            approved_by="api_direct" if request.auto_approve else None,
            approved_at=datetime.utcnow() if request.auto_approve else None,
            executed_at=datetime.utcnow(),
            error=None,
            retry_count=0,
            created_at=datetime.utcnow(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(e)}",
        )
