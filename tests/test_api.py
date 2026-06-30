"""Tests for API endpoints"""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.models.db_models import TaskStatus


class TestHealthEndpoint:
    """Tests for health check endpoints"""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint returns 200"""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data


class TestTaskEndpoints:
    """Tests for task management endpoints"""

    @pytest.mark.asyncio
    async def test_create_task(self, client: AsyncClient):
        """Test creating a task"""
        response = await client.post(
            "/api/tasks",
            json={
                "input": {
                    "request": "I need a refund for order #12345",
                    "user_id": "user_123",
                },
                "priority": 3,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["priority"] == 3

    @pytest.mark.asyncio
    async def test_create_task_missing_input(self, client: AsyncClient):
        """Test creating a task without input fails"""
        response = await client.post("/api/tasks", json={"priority": 3})

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_tasks(self, client: AsyncClient):
        """Test listing tasks"""
        # Create a task first
        await client.post(
            "/api/tasks", json={"input": {"request": "Test request"}, "priority": 5}
        )

        response = await client.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_task(self, client: AsyncClient):
        """Test getting a specific task"""
        # Create a task
        create_response = await client.post(
            "/api/tasks", json={"input": {"request": "Test request"}, "priority": 5}
        )
        task_id = create_response.json()["id"]

        # Get the task
        response = await client.get(f"/api/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, client: AsyncClient):
        """Test getting a nonexistent task returns 404"""
        fake_id = str(uuid4())
        response = await client.get(f"/api/tasks/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_tasks_with_filter(self, client: AsyncClient):
        """Test listing tasks with status filter"""
        response = await client.get("/api/tasks?status=pending")

        assert response.status_code == 200
        data = response.json()
        # All returned tasks should have pending status
        for task in data["tasks"]:
            assert task["status"] == "pending"


class TestToolEndpoints:
    """Tests for tool management endpoints"""

    @pytest.mark.asyncio
    async def test_list_tools(self, client: AsyncClient):
        """Test listing available tools"""
        response = await client.get("/api/tools")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "total" in data
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_get_tool(self, client: AsyncClient):
        """Test getting a specific tool"""
        response = await client.get("/api/tools/refund_user")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "refund_user"
        assert data["category"] == "billing"

    @pytest.mark.asyncio
    async def test_get_nonexistent_tool(self, client: AsyncClient):
        """Test getting a nonexistent tool returns 404"""
        response = await client.get("/api/tools/nonexistent_tool")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_tool(self, client: AsyncClient):
        """Test executing a tool directly"""
        response = await client.post(
            "/api/tools/refund_user/execute",
            json={
                "tool_input": {"order_id": "ORD-12345", "amount": 50.00},
                "auto_approve": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tool_name"] == "refund_user"
        assert data["status"] == "completed"


class TestAuditEndpoints:
    """Tests for audit endpoints"""

    @pytest.mark.asyncio
    async def test_get_task_thoughts(self, client: AsyncClient):
        """Test getting task thoughts"""
        # Create a task
        create_response = await client.post(
            "/api/tasks", json={"input": {"request": "Test request"}, "priority": 5}
        )
        task_id = create_response.json()["id"]

        # Get thoughts (may be empty for new task)
        response = await client.get(f"/api/audit/tasks/{task_id}/thoughts")

        assert response.status_code == 200
        data = response.json()
        assert "thoughts" in data

    @pytest.mark.asyncio
    async def test_get_task_executions(self, client: AsyncClient):
        """Test getting task tool executions"""
        # Create a task
        create_response = await client.post(
            "/api/tasks", json={"input": {"request": "Test request"}, "priority": 5}
        )
        task_id = create_response.json()["id"]

        # Get executions (may be empty for new task)
        response = await client.get(f"/api/audit/tasks/{task_id}/executions")

        assert response.status_code == 200
        data = response.json()
        assert "executions" in data

    @pytest.mark.asyncio
    async def test_get_task_timeline(self, client: AsyncClient):
        """Test getting task timeline"""
        # Create a task
        create_response = await client.post(
            "/api/tasks", json={"input": {"request": "Test request"}, "priority": 5}
        )
        task_id = create_response.json()["id"]

        # Get timeline
        response = await client.get(f"/api/audit/tasks/{task_id}/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "events" in data
