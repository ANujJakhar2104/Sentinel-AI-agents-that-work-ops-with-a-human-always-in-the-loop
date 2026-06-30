"""Tests for tool functionality"""

import pytest

from app.tools.base import BaseTool, ValidationResult
from app.tools.registry import ToolRegistry
from app.tools.billing import RefundUserTool, CreditUserTool
from app.tools.auth import ResetApiKeyTool, BlockUserTool
from app.tools.support import SendEmailTool, CreateTicketTool


class TestBaseTool:
    """Tests for the base tool class"""

    def test_tool_validation_success(self):
        """Test successful input validation"""
        tool = RefundUserTool()
        result = tool.validate_input({"order_id": "12345", "amount": 50.00})

        assert result.valid is True

    def test_tool_validation_missing_required(self):
        """Test validation fails for missing required field"""
        tool = RefundUserTool()
        result = tool.validate_input({"amount": 50.00})

        assert result.valid is False
        assert "order_id" in result.error

    def test_tool_validation_wrong_type(self):
        """Test validation fails for wrong type"""
        tool = RefundUserTool()
        result = tool.validate_input({"order_id": "12345", "amount": "not a number"})

        assert result.valid is False

    def test_tool_max_amount_validation(self):
        """Test validation fails for amount exceeding max"""
        tool = RefundUserTool()
        result = tool.validate_input(
            {
                "order_id": "12345",
                "amount": 5000.00,  # Exceeds max_amount of 1000
            }
        )

        assert result.valid is False
        assert "exceeds maximum" in result.error.lower()

    def test_tool_get_info(self):
        """Test getting tool info"""
        tool = RefundUserTool()
        info = tool.get_info()

        assert info["name"] == "refund_user"
        assert info["requires_approval"] is True
        assert info["category"] == "billing"


class TestToolRegistry:
    """Tests for the tool registry"""

    def test_register_tool(self):
        """Test registering a tool"""
        ToolRegistry._tools = {}  # Clear registry

        ToolRegistry.register(RefundUserTool)

        assert "refund_user" in ToolRegistry._tools

    def test_get_tool(self):
        """Test getting a tool instance"""
        ToolRegistry._tools = {}
        ToolRegistry.register(RefundUserTool)

        tool = ToolRegistry.get_tool("refund_user")

        assert tool is not None
        assert tool.name == "refund_user"

    def test_get_nonexistent_tool(self):
        """Test getting a nonexistent tool returns None"""
        ToolRegistry._tools = {}

        tool = ToolRegistry.get_tool("nonexistent_tool")

        assert tool is None

    def test_list_tools(self):
        """Test listing all tools"""
        ToolRegistry._tools = {}
        ToolRegistry.register(RefundUserTool)
        ToolRegistry.register(ResetApiKeyTool)

        tools = ToolRegistry.list_tools()

        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert "refund_user" in tool_names
        assert "reset_api_key" in tool_names

    def test_tool_exists(self):
        """Test checking if tool exists"""
        ToolRegistry._tools = {}
        ToolRegistry.register(RefundUserTool)

        assert ToolRegistry.tool_exists("refund_user") is True
        assert ToolRegistry.tool_exists("nonexistent") is False


class TestBillingTools:
    """Tests for billing tools"""

    @pytest.mark.asyncio
    async def test_refund_user(self):
        """Test refund_user tool execution"""
        tool = RefundUserTool()
        result = await tool.execute(
            order_id="ORD-12345",
            amount=99.99,
            reason="Customer request",
            user_id="user_123",
        )

        assert result["success"] is True
        assert "refund_id" in result
        assert result["amount"] == 99.99

    @pytest.mark.asyncio
    async def test_credit_user(self):
        """Test credit_user tool execution"""
        tool = CreditUserTool()
        result = await tool.execute(
            user_id="user_123", amount=50.00, reason="Goodwill credit"
        )

        assert result["success"] is True
        assert "credit_id" in result
        assert result["amount"] == 50.00


class TestAuthTools:
    """Tests for auth tools"""

    @pytest.mark.asyncio
    async def test_reset_api_key(self):
        """Test reset_api_key tool execution"""
        tool = ResetApiKeyTool()
        result = await tool.execute(
            user_id="user_123", reason="Security concern", invalidate_sessions=True
        )

        assert result["success"] is True
        assert "new_api_key" in result
        assert result["sessions_invalidated"] is True

    @pytest.mark.asyncio
    async def test_block_user(self):
        """Test block_user tool execution"""
        tool = BlockUserTool()
        result = await tool.execute(
            user_id="user_123", reason="Policy violation", duration_hours=24
        )

        assert result["success"] is True
        assert result["is_permanent"] is False


class TestSupportTools:
    """Tests for support tools"""

    @pytest.mark.asyncio
    async def test_send_email(self):
        """Test send_email tool execution"""
        tool = SendEmailTool()
        result = await tool.execute(
            user_id="user_123", subject="Test Subject", body="Test body content"
        )

        assert result["success"] is True
        assert "email_id" in result

    @pytest.mark.asyncio
    async def test_create_ticket(self):
        """Test create_ticket tool execution"""
        tool = CreateTicketTool()
        result = await tool.execute(
            user_id="user_123",
            subject="Need help",
            description="Customer needs assistance",
            priority="high",
        )

        assert result["success"] is True
        assert "ticket_id" in result
        assert result["priority"] == "high"
