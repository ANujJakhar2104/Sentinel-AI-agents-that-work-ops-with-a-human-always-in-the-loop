"""Tool registry for managing available tools"""

from typing import Dict, List, Any, Optional, Type
import logging

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for all available tools.

    Tools are registered at startup and can be retrieved by name.
    The registry provides:
    - Tool lookup by name
    - List of all tools
    - Tool info for agent consumption
    """

    _tools: Dict[str, Type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_class: Type[BaseTool]) -> None:
        """
        Register a tool class.

        Args:
            tool_class: The tool class to register
        """
        instance = tool_class()
        cls._tools[instance.name] = tool_class
        logger.info(f"Registered tool: {instance.name}")

    @classmethod
    def get_tool(cls, name: str) -> Optional[BaseTool]:
        """
        Get a tool instance by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        tool_class = cls._tools.get(name)
        if tool_class:
            return tool_class()
        return None

    @classmethod
    def get_tool_info(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool information by name.

        Args:
            name: Tool name

        Returns:
            Tool info dict or None if not found
        """
        tool = cls.get_tool(name)
        if tool:
            return tool.get_info()
        return None

    @classmethod
    def list_tools(cls) -> List[Dict[str, Any]]:
        """
        List all registered tools.

        Returns:
            List of tool info dicts
        """
        tools = []
        for name in cls._tools:
            info = cls.get_tool_info(name)
            if info:
                tools.append(info)
        return tools

    @classmethod
    def list_tools_by_category(cls, category: str) -> List[Dict[str, Any]]:
        """
        List tools by category.

        Args:
            category: Category to filter by

        Returns:
            List of tool info dicts
        """
        return [info for info in cls.list_tools() if info.get("category") == category]

    @classmethod
    def tool_exists(cls, name: str) -> bool:
        """
        Check if a tool exists.

        Args:
            name: Tool name

        Returns:
            True if tool exists
        """
        return name in cls._tools


def register_all_tools():
    """Register all available tools"""
    from app.tools.billing import RefundUserTool, CreditUserTool
    from app.tools.auth import ResetApiKeyTool, BlockUserTool
    from app.tools.support import SendEmailTool, CreateTicketTool

    # Billing tools
    ToolRegistry.register(RefundUserTool)
    ToolRegistry.register(CreditUserTool)

    # Auth tools
    ToolRegistry.register(ResetApiKeyTool)
    ToolRegistry.register(BlockUserTool)

    # Support tools
    ToolRegistry.register(SendEmailTool)
    ToolRegistry.register(CreateTicketTool)

    logger.info(f"Registered {len(ToolRegistry._tools)} tools")
