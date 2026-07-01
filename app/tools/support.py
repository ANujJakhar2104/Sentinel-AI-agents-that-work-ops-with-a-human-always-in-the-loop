"""Support tools for customer service operations"""

from typing import Dict, Any, List
import uuid
from datetime import datetime

from app.tools.base import BaseTool


class SendEmailTool(BaseTool):
    """Send an email to a user"""

    name = "send_email"
    description = "Send an email to a user. Use for notifications, confirmations, and support responses."
    category = "support"
    version = "1.0.0"

    input_schema = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User ID to send email to"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body content"},
            "template": {
                "type": "string",
                "description": "Email template to use (optional)",
            },
            "cc": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Email addresses to CC",
            },
        },
        "required": ["subject", "body"],
    }

    requires_approval = False
    allowed_roles = ["agent", "support_agent", "admin"]
    critical_on_failure = False

        async def execute(
        self,
        subject: str = "Notification",
        body: str = "",
        user_id: str = "unknown",
        template: str = None,
        cc: List[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send email.

        In production, this would:
        1. Get user email from database
        2. Render template if provided
        3. Send via email provider (SendGrid, SES, etc.)
        4. Log for audit
        """
        email_id = f"EM-{uuid.uuid4().hex[:8].upper()}"

        return {
            "success": True,
            "email_id": email_id,
            "user_id": user_id,
            "subject": subject,
            "template": template,
            "cc": cc or [],
            "sent_at": datetime.utcnow().isoformat(),
            "message": f"Email sent to user {user_id}",
        }


class CreateTicketTool(BaseTool):
    """Create a support ticket"""

    name = "create_ticket"
    description = "Create a support ticket for human follow-up. Use for complex issues requiring human intervention."
    category = "support"
    version = "1.0.0"

    input_schema = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User ID the ticket is for"},
            "subject": {"type": "string", "description": "Ticket subject"},
            "description": {
                "type": "string",
                "description": "Detailed description of the issue",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Ticket priority",
            },
            "category": {"type": "string", "description": "Ticket category"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for categorization",
            },
            "assign_to": {
                "type": "string",
                "description": "Team or person to assign to",
            },
        },
        "required": ["user_id", "subject", "description"],
    }

    requires_approval = False
    allowed_roles = ["agent", "support_agent", "admin"]
    critical_on_failure = False

    async def execute(
        self,
        user_id: str,
        subject: str,
        description: str,
        priority: str = "medium",
        category: str = "general",
        tags: List[str] = None,
        assign_to: str = None,
    ) -> Dict[str, Any]:
        """
        Create support ticket.

        In production, this would:
        1. Create ticket in helpdesk system (Zendesk, Freshdesk, etc.)
        2. Link to user record
        3. Assign to appropriate team
        4. Send confirmation to user
        """
        ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"

        return {
            "success": True,
            "ticket_id": ticket_id,
            "user_id": user_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "category": category,
            "tags": tags or [],
            "assigned_to": assign_to or "support_team",
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
            "message": f"Ticket {ticket_id} created for user {user_id}",
        }


class GetUserInfoTool(BaseTool):
    """Retrieve user information"""

    name = "get_user_info"
    description = "Retrieve user account information for context. Use to understand user's current state."
    category = "support"
    version = "1.0.0"

    input_schema = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User ID to look up"},
            "include_orders": {
                "type": "boolean",
                "description": "Include recent orders",
            },
            "include_subscriptions": {
                "type": "boolean",
                "description": "Include subscription info",
            },
        },
        "required": ["user_id"],
    }

    requires_approval = False
    allowed_roles = ["agent", "support_agent", "admin"]
    critical_on_failure = False

    async def execute(
        self,
        user_id: str,
        include_orders: bool = False,
        include_subscriptions: bool = False,
    ) -> Dict[str, Any]:
        """
        Get user info.

        In production, this would query the user database.
        """
        # Simulated user data
        return {
            "success": True,
            "user_id": user_id,
            "email": f"user_{user_id}@example.com",
            "account_status": "active",
            "created_at": "2023-01-15T00:00:00Z",
            "last_login": datetime.utcnow().isoformat(),
            "subscription_tier": "pro",
            "balance": 0.00,
            "orders_count": 5,
            "support_tickets_count": 2,
            "recent_orders": []
            if not include_orders
            else [
                {"order_id": "ORD-12345", "status": "delivered", "total": 149.99},
            ],
            "subscriptions": []
            if not include_subscriptions
            else [{"plan": "pro", "status": "active", "renews_at": "2024-02-01"}],
            "message": f"User info retrieved for {user_id}",
        }
