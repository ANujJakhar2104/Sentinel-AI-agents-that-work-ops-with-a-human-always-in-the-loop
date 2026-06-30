"""Base tool class for all tools"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of tool input validation"""

    valid: bool
    error: Optional[str] = None


class BaseTool(ABC):
    """
    Base class for all tools that agents can execute.

    Tools must define:
    - name: Unique identifier
    - description: What the tool does
    - input_schema: JSON schema for inputs
    - execute: Async method that performs the action

    Tools can optionally define:
    - requires_approval: Whether human approval is needed
    - allowed_roles: Who can use this tool
    - max_amount: For financial tools
    - critical_on_failure: Whether failure stops the task
    """

    name: str = "base_tool"
    description: str = "Base tool class"
    category: str = "general"
    version: str = "1.0.0"

    # Input schema (JSON Schema format)
    input_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    # Safety settings
    requires_approval: bool = False
    allowed_roles: List[str] = ["agent", "admin", "support_agent"]
    max_amount: Optional[float] = None  # For financial tools
    critical_on_failure: bool = False

    def validate_input(self, input_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate input against the schema.

        Args:
            input_data: Input to validate

        Returns:
            ValidationResult indicating success or failure
        """
        if not isinstance(input_data, dict):
            return ValidationResult(valid=False, error="Input must be a dictionary")

        # Check required fields
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in input_data:
                return ValidationResult(
                    valid=False, error=f"Missing required field: {field}"
                )

        # Check types
        properties = self.input_schema.get("properties", {})
        for field, value in input_data.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    return ValidationResult(
                        valid=False,
                        error=f"Field '{field}' must be of type {expected_type}",
                    )

        # Check max_amount for financial tools
        if self.max_amount is not None:
            amount = input_data.get("amount")
            if amount is not None and float(amount) > self.max_amount:
                return ValidationResult(
                    valid=False,
                    error=f"Amount {amount} exceeds maximum {self.max_amount}",
                )

        return ValidationResult(valid=True)

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON schema type"""
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # Unknown type, skip validation

        return isinstance(value, expected_python_type)

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool.

        Args:
            **kwargs: Tool input parameters

        Returns:
            Dict containing execution result
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """Get tool information for registry"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "input_schema": self.input_schema,
            "requires_approval": self.requires_approval,
            "allowed_roles": self.allowed_roles,
            "max_amount": self.max_amount,
            "critical_on_failure": self.critical_on_failure,
        }
