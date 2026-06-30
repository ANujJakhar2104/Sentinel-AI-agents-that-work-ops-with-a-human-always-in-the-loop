"""FastAPI application entry point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, check_db_connection
from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.tools import router as tools_router
from app.api.audit import router as audit_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    print("Starting up Agentic Ops Platform...")

    # Initialize database tables
    try:
        await init_db()
        print("Database tables initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize database tables: {e}")

    # Register tools
    from app.tools.registry import register_all_tools

    register_all_tools()
    print("Tools registered")

    yield

    # Shutdown
    print("Shutting down Agentic Ops Platform...")


# Create FastAPI application
app = FastAPI(
    title="Agentic Ops Platform",
    description="""
A reliable framework for autonomous operations using AI agents.

## Features

- **State Machine Orchestration**: Central orchestrator manages agent workflows
- **Specialized Agents**: Classifier, ToolRunner, and Escalator agents
- **Full Audit Trail**: Every agent thought and action is logged
- **Safe Tool Execution**: Backend functions executed via defined interface
- **Async Task Processing**: Celery + Redis for background jobs

## Workflow

1. Create a task with input data
2. Task is queued for processing
3. Orchestrator coordinates agents to process the task
4. Monitor progress via task status and audit logs
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(tools_router)
app.include_router(audit_router)


# Root endpoint redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation"""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/docs")
