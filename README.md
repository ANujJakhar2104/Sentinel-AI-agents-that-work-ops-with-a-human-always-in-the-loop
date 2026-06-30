# Agentic Ops Platform

A reliable framework for autonomous operations using state-machine-driven AI agent orchestration. Internal operations (support, integrity) are often manual and brittle - this platform provides robust, auditable task execution with specialized AI agents.

## Features

- **State Machine Orchestration**: Central orchestrator manages agent workflows with defined state transitions
- **Specialized Agents**: Purpose-built agents for classification, tool execution, and escalation
- **Full Audit Trail**: Every agent thought and action logged to Postgres for compliance
- **Safe Tool Execution**: Agents execute backend functions via a defined, permissioned interface
- **Async Task Processing**: Celery + Redis for reliable background job processing
- **Real-time Monitoring**: Track task progress, agent decisions, and system health

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Layer | Python FastAPI |
| Task Queue | Celery + Redis |
| LLM Framework | LangChain |
| Default LLM | OpenAI GPT-4 |
| Database | Postgres |
| Deployment | Railway |

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Agentic Ops Platform                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────┐ │
│  │   FastAPI    │────▶│    Redis     │────▶│      Celery Workers          │ │
│  │   (API)      │     │   (Broker)   │     │                              │ │
│  └──────────────┘     └──────────────┘     │  ┌────────────────────────┐  │ │
│         │                                   │  │     Orchestrator       │  │ │
│         │                                   │  │   ┌────────────────┐   │  │ │
│         ▼                                   │  │   │ State Machine  │   │  │ │
│  ┌──────────────┐                          │  │   │    Engine      │   │  │ │
│  │   Postgres   │◀─────────────────────────│  │   └───────┬────────┘   │  │ │
│  │  (Storage)   │                          │  │           │            │  │ │
│  └──────────────┘                          │  │           ▼            │  │ │
│         │                                   │  │  ┌─────────────────┐  │  │ │
│         │                                   │  │  │    Agents       │  │  │ │
│         ▼                                   │  │  │ ┌─────────────┐ │  │  │ │
│  ┌──────────────┐                          │  │  │ │ Classifier  │ │  │  │ │
│  │  Audit Logs  │                          │  │  │ ├─────────────┤ │  │  │ │
│  │  Thoughts &  │                          │  │  │ │ ToolRunner  │ │  │  │ │
│  │  Actions     │                          │  │  │ ├─────────────┤ │  │  │ │
│  └──────────────┘                          │  │  │ │ Escalator   │ │  │  │ │
│                                            │  │  │ └─────────────┘ │  │  │ │
│                                            │  │  └─────────────────┘  │  │ │
│                                            │  └────────────────────────┘  │ │
│                                            └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### State Machine Flow

```
                    ┌─────────────────────────────────────────────────┐
                    │                  TASK LIFECYCLE                   │
                    └─────────────────────────────────────────────────┘
                                            
    ┌────────┐      ┌─────────────┐      ┌──────────────┐      ┌───────────┐
    │ PENDING│─────▶│ CLASSIFYING │─────▶│  EXECUTING   │─────▶│ COMPLETED │
    └────────┘      └─────────────┘      └──────────────┘      └───────────┘
         │                │                      │                   
         │                │                      │                   
         │                ▼                      ▼                   
         │          ┌───────────┐          ┌───────────┐            
         │          │ ESCALATED │          │  FAILED   │            
         │          └───────────┘          └───────────┘            
         │                                                             
         └──────────────────────────────────────────────────────────────
                                    CANCELLED
```

### Agent Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                 │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    State Machine Engine                        │  │
│  │                                                                │  │
│  │   • Manages task lifecycle                                     │  │
│  │   • Routes to appropriate agents                               │  │
│  │   • Handles state transitions                                  │  │
│  │   • Implements retry logic                                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │  CLASSIFIER  │ │  TOOLRUNNER  │ │  ESCALATOR   │
           │    AGENT     │ │    AGENT     │ │    AGENT     │
           ├──────────────┤ ├──────────────┤ ├──────────────┤
           │              │ │              │ │              │
           │ Analyzes     │ │ Executes     │ │ Notifies     │
           │ incoming     │ │ approved     │ │ humans for   │
           │ requests     │ │ tools        │ │ complex      │
           │              │ │              │ │ decisions    │
           │ Determines:  │ │ Examples:    │ │              │
           │ • Task type  │ │ • refund_user│ │ Creates:     │
           │ • Priority   │ │ • reset_key  │ │ • Alerts     │
           │ • Tools needed│ │ • send_email │ │ • Tickets    │
           │ • Confidence │ │ • block_user │ │ • Escalations│
           │              │ │              │ │              │
           └──────────────┘ └──────────────┘ └──────────────┘
                    │               │               │
                    └───────────────┴───────────────┘
                                    │
                                    ▼
           ┌─────────────────────────────────────────────────────┐
           │                     TOOL LAYER                       │
           │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
           │  │   Billing   │  │     Auth    │  │    Support  │  │
           │  │    Tools    │  │    Tools    │  │     Tools   │  │
           │  └─────────────┘  └─────────────┘  └─────────────┘  │
           └─────────────────────────────────────────────────────┘
```

### Agent Responsibilities

#### 1. Classifier Agent
- **Purpose**: Analyzes incoming requests and determines the appropriate action
- **Inputs**: User request, context, historical patterns
- **Outputs**: Task classification, required tools, confidence score
- **Example**: "I need a refund for order #12345" → Classification: `refund_request`, Tools: `refund_user`

#### 2. ToolRunner Agent
- **Purpose**: Executes approved tools with parameters extracted from context
- **Safety**: All tool executions are pre-validated and logged
- **Outputs**: Execution result, side effects, audit trail
- **Example**: Executes `refund_user(order_id="12345", amount=99.99, reason="customer_request")`

#### 3. Escalator Agent
- **Purpose**: Handles cases requiring human intervention
- **Triggers**: Low confidence, sensitive operations, policy violations
- **Outputs**: Escalation ticket, context summary, recommended actions
- **Example**: Creates ticket: "User requested account deletion with active subscriptions"

### Audit & Compliance

Every operation is logged with:

```json
{
  "task_id": "uuid",
  "agent": "classifier",
  "thought": "Analyzing request: customer wants refund for order #12345",
  "action": "classify",
  "action_input": {"request": "refund order #12345"},
  "observation": "Classified as refund_request with 0.95 confidence",
  "timestamp": "2024-01-15T10:30:00Z",
  "metadata": {
    "model": "gpt-4",
    "tokens_used": 150,
    "latency_ms": 450
  }
}
```

## Project Structure

```
agentic-ops-platform/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Configuration settings
│   ├── database.py                # Database connection
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic models
│   │   └── db_models.py           # SQLAlchemy models
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                # Base agent class
│   │   ├── orchestrator.py        # Central orchestrator
│   │   ├── classifier.py          # Classification agent
│   │   ├── tool_runner.py         # Tool execution agent
│   │   ├── escalator.py           # Escalation agent
│   │   └── state_machine.py       # State machine definitions
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                # Base tool class
│   │   ├── billing.py             # Billing tools (refund, credit)
│   │   ├── auth.py                # Auth tools (reset_key, block_user)
│   │   ├── support.py             # Support tools (send_email, create_ticket)
│   │   └── registry.py            # Tool registry
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery configuration
│   │   └── agent_tasks.py         # Agent task definitions
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── tasks.py               # Task management endpoints
│   │   ├── tools.py               # Tool management endpoints
│   │   ├── audit.py               # Audit log endpoints
│   │   └── health.py              # Health check endpoints
│   │
│   └── services/
│       ├── __init__.py
│       ├── audit.py               # Audit logging service
│       └── notification.py        # Notification service
│
├── tests/
│   ├── conftest.py
│   ├── test_agents.py
│   ├── test_tools.py
│   └── test_api.py
│
├── requirements.txt
├── pyproject.toml
├── .env.example
├── Procfile
├── runtime.txt
└── README.md
```

## Database Schema

### Tasks Table

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    task_type VARCHAR(100),
    priority INTEGER DEFAULT 5,
    
    -- Input/Output
    input JSONB NOT NULL,
    output JSONB,
    error TEXT,
    
    -- Classification
    classification JSONB,
    confidence_score FLOAT,
    
    -- State Machine
    current_state VARCHAR(50) NOT NULL,
    state_history JSONB DEFAULT '[]',
    
    -- Tracking
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);
```

### Agent Thoughts (Audit) Table

```sql
CREATE TABLE agent_thoughts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    
    -- Agent Info
    agent_name VARCHAR(100) NOT NULL,
    agent_version VARCHAR(50),
    
    -- Thought Process
    thought TEXT,
    action VARCHAR(100),
    action_input JSONB,
    observation TEXT,
    
    -- Execution Details
    model VARCHAR(100),
    tokens_used INTEGER,
    latency_ms INTEGER,
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Additional Context
    metadata JSONB DEFAULT '{}'
);
```

### Tool Executions Table

```sql
CREATE TABLE tool_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    thought_id UUID REFERENCES agent_thoughts(id),
    
    -- Tool Info
    tool_name VARCHAR(100) NOT NULL,
    tool_input JSONB NOT NULL,
    tool_output JSONB,
    
    -- Execution Status
    status VARCHAR(50) NOT NULL,  -- approved, executed, failed
    approved_by VARCHAR(100),      -- agent or human
    approved_at TIMESTAMP,
    executed_at TIMESTAMP,
    
    -- Error Handling
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

### Task Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks` | POST | Create a new task |
| `/api/tasks` | GET | List tasks with filtering |
| `/api/tasks/{id}` | GET | Get task details |
| `/api/tasks/{id}/cancel` | POST | Cancel a running task |
| `/api/tasks/{id}/retry` | POST | Retry a failed task |

### Tool Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tools` | GET | List available tools |
| `/api/tools/{name}` | GET | Get tool details |
| `/api/tools/{name}/execute` | POST | Execute a tool directly |

### Audit & Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/audit/tasks/{id}/thoughts` | GET | Get all agent thoughts for a task |
| `/api/audit/tasks/{id}/executions` | GET | Get all tool executions for a task |
| `/api/audit/tasks/{id}/timeline` | GET | Get complete execution timeline |
| `/health` | GET | Health check |
| `/metrics` | GET | System metrics |

## Tool Interface

Tools are defined with a standardized interface for safety and auditability:

```python
from app.tools.base import BaseTool

class RefundUserTool(BaseTool):
    name = "refund_user"
    description = "Process a refund for a user order"
    
    # Define input schema
    input_schema = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "Order ID to refund"},
            "amount": {"type": "number", "description": "Refund amount"},
            "reason": {"type": "string", "description": "Reason for refund"}
        },
        "required": ["order_id", "amount"]
    }
    
    # Define safety constraints
    requires_approval = True
    max_amount = 1000.00
    allowed_roles = ["support_agent", "admin"]
    
    async def execute(self, order_id: str, amount: float, reason: str = ""):
        # Implementation
        pass
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/agentic_ops

# Redis (Celery Broker)
REDIS_URL=redis://localhost:6379/0

# LLM Configuration
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4

# API Authentication
API_KEY=your-secure-api-key

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
MAX_TASK_RETRIES=3
TASK_TIMEOUT_SECONDS=300
```

## Local Development

### Prerequisites

- Python 3.11+
- Postgres 14+
- Redis 6+

### Setup

```bash
# Clone the repository
git clone git@github.com:ritwikareddykancharla/agentic-ops-platform.git
cd agentic-ops-platform

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your values

# Run database migrations
alembic upgrade head

# Start Redis (using Docker)
docker run -d -p 6379:6379 redis:alpine

# Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# Start FastAPI server
uvicorn app.main:app --reload
```

### Running with Docker Compose

```bash
docker-compose up -d
```

## Railway Deployment

### Services Required

1. **Postgres** - Database for tasks, audit logs
2. **Redis** - Celery broker and result backend
3. **Web Service** - FastAPI application
4. **Worker Service** - Celery worker

### Deployment Steps

1. Create a new Railway project
2. Add Postgres and Redis services
3. Deploy from GitHub:
   - Main service: FastAPI app (Procfile)
   - Worker service: Celery worker

### Procfile

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.tasks.celery_app worker --loglevel=info
```

## Example Usage

### Create a Task

```bash
curl -X POST "https://your-app.railway.app/api/tasks" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "request": "I need a refund for order #12345. The product was defective.",
      "user_id": "user_789",
      "context": {"order_total": 149.99}
    },
    "priority": 3
  }'
```

### Response

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Task created and queued for processing"
}
```

### Get Task Status

```bash
curl "https://your-app.railway.app/api/tasks/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your-api-key"
```

### Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "task_type": "refund_request",
  "current_state": "completed",
  "input": {
    "request": "I need a refund for order #12345..."
  },
  "output": {
    "refund_id": "REF-98765",
    "amount_refunded": 149.99,
    "message": "Refund processed successfully"
  },
  "classification": {
    "type": "refund_request",
    "confidence": 0.95,
    "tools_needed": ["refund_user"]
  },
  "created_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:01:30Z"
}
```

## Implementation Phases

| Phase | Status | Tasks |
|-------|--------|-------|
| **1. Foundation** | Pending | Project setup, database models, config |
| **2. Core Agents** | Pending | Base agent, orchestrator, state machine |
| **3. Specialized Agents** | Pending | Classifier, ToolRunner, Escalator |
| **4. Tool Layer** | Pending | Tool registry, billing/auth/support tools |
| **5. Task Queue** | Pending | Celery setup, task definitions |
| **6. API Layer** | Pending | REST endpoints, authentication |
| **7. Audit & Logging** | Pending | Thought/action logging, timeline |
| **8. Testing** | Pending | Unit tests, integration tests |
| **9. Deployment** | Pending | Railway config, documentation |

## License

MIT License - see [LICENSE](LICENSE) for details.
