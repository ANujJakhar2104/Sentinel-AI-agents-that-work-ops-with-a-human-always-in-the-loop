"""Authentication tools for user management"""

from typing import Dict, Any
import uuid
import secrets
from datetime import datetime, timedelta

from app.tools.base import BaseTool


class ResetApiKeyTool(BaseTool):
    """Reset a user's API key"""

    name = "reset_api_key"
    description = (
        "Reset a user's API key, invalidating the old one and generating a new one"
    )
    category = "auth"
    version = "1.0.0"

    input_schema = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "User ID to reset API key for",
            },
            "reason": {"type": "string", "description": "Reason for reset"},
            "invalidate_sessions": {
                "type": "boolean",
                "description": "Whether to invalidate all active sessions",
            },
        },
        "required": ["user_id"],
    }

    requires_approval = False  # User-initiated actions don't need approval
    allowed_roles = ["agent", "support_agent", "admin"]
    critical_on_failure = False

    async def execute(
        self, user_id: str, reason: str = "", invalidate_sessions: bool = True
    ) -> Dict[str, Any]:
        """
        Reset API key.

        In production, this would:
        1. Validate user exists
        2. Generate new API key
        3. Invalidate old key
        4. Optionally invalidate sessions
        5. Send notification to user
        """
        new_key = f"sk_{secrets.token_urlsafe(32)}"
        old_key_prefix = "sk_***...***"  # Don't expose old key

        return {
            "success": True,
            "user_id": user_id,
            "new_api_key": new_key,
            "old_key_prefix": old_key_prefix,
            "reason": reason,
            "sessions_invalidated": invalidate_sessions,
            "reset_at": datetime.utcnow().isoformat(),
            "message": f"API key reset for user {user_id}",
        }


class BlockUserTool(BaseTool):
    """Block a user account"""

    name = "block_user"
    description = "Block a user account, preventing access. Use for security issues or policy violations."
    category = "auth"
    version = "1.0.0"

    input_schema = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User ID to block"},
            "reason": {"type": "string", "description": "Reason for blocking"},
            "duration_hours": {
                "type": "integer",
                "description": "Duration of block in hours (0 for permanent)",
            },
            "notify_user": {
                "type": "boolean",
                "description": "Whether to notify the user",
            },
        },
        "required": ["user_id", "reason"],
    }

    requires_approval = True  # Blocking users requires approval
    allowed_roles = ["admin", "moderator"]
    critical_on_failure = True

    async def execute(
        self,
        user_id: str,
        reason: str,
        duration_hours: int = 0,
        notify_user: bool = True,
    ) -> Dict[str, Any]:
        """
        Block user account.

        In production, this would:
        1. Validate user exists
        2. Create block record
        3. Invalidate all sessions
        4. Revoke API keys
        5. Log for audit
        6. Optionally notify user
        """
        block_id = f"BLK-{uuid.uuid4().hex[:8].upper()}"

        expires_at = None
        if duration_hours > 0:
            expires_at = (
                datetime.utcnow() + timedelta(hours=duration_hours)
            ).isoformat()

        return {
            "success": True,
            "block_id": block_id,
            "user_id": user_id,
            "reason": reason,
            "duration_hours": duration_hours,
            "expires_at": expires_at,
            "is_permanent": duration_hours == 0,
            "notified": notify_user,
            "blocked_at": datetime.utcnow().isoformat(),
            "message": f"User {user_id} has been blocked",
        }
