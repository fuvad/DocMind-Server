# DocMind — Server

FastAPI backend for DocMind, an AI-powered document intelligence platform. Handles document ingestion, RAG retrieval, multi-agent orchestration, and chat with LLM-powered responses.

## Tech Stack

- **Framework:** FastAPI + Uvicorn
- **Language:** Python 3.12
- **Package Manager:** Poetry
- **Database:** Supabase (PostgreSQL + pgvector)
- **Task Queue:** Celery + Redis
- **LLM & Embeddings:** OpenAI (`gpt-4o-mini`, `text-embedding-3-small`) via LangChain
- **Agent Orchestration:** LangGraph (Supervisor multi-agent architecture)
- **Document Processing:** Unstructured (`unstructured[all-docs]`)
- **Web Scraping:** ScrapingBee
- **Object Storage:** Tigris (S3-compatible) via Boto3
- **Authentication:** Clerk (JWT verification)
- **Observability:** Structlog (structured logging), LangSmith (LLM tracing)
- **Evaluation:** RAGAS
- **Deployment:** Docker, AWS ECS Fargate, ECR, ElastiCache, ALB, CloudFront

## Project Structure

```
server/
├── src/
│   ├── agents/
│   │   ├── simple_agent/        # Basic ReAct agent
│   │   └── supervisor_agent/    # Supervisor multi-agent (RAG + Web Search sub-agents)
│   ├── config/
│   │   ├── index.py             # App configuration & env validation
│   │   └── logging.py           # Structured logging setup
│   ├── middleware/
│   │   └── logging_middleware.py # Request/response logging
│   ├── models/
│   │   └── index.py             # Pydantic models & enums
│   ├── rag/
│   │   ├── ingestion/
│   │   │   ├── index.py         # Document processing pipeline
│   │   │   └── utils.py         # Partitioning, chunking, summarization utilities
│   │   └── retrieval/
│   │       ├── index.py         # Retrieval strategies (vector, hybrid, multi-query)
│   │       └── utils.py         # Context building, RRF fusion, prompt preparation
│   ├── routes/
│   │   ├── chatRoutes.py        # Chat CRUD endpoints
│   │   ├── projectRoutes.py     # Project CRUD, settings, send message (streaming)
│   │   ├── projectFilesRoutes.py # File upload, URL ingestion, document management
│   │   └── userRoutes.py        # User creation (Clerk webhook)
│   ├── services/
│   │   ├── awsS3.py             # S3 client (Tigris)
│   │   ├── celery.py            # Celery app & background tasks
│   │   ├── clerkAuth.py         # Clerk JWT authentication
│   │   ├── llm.py               # OpenAI LLM & embedding model instances
│   │   ├── supabase.py          # Supabase client
│   │   └── webScrapper.py       # ScrapingBee client
│   ├── utils/                   # Shared utility functions
│   └── server.py                # FastAPI app entry point
├── supabase/
│   └── migrations/              # SQL migrations (schema + pgvector functions)
├── rag_evaluation/
│   ├── scripts/                 # Data collection & evaluation scripts
│   ├── notebooks/               # Jupyter notebooks for RAGAS metrics
│   └── datasets/                # Evaluation results (CSV)
├── notebooks/                   # Experimentation notebooks (agents, guardrails)
├── logs/                        # Application & worker logs
├── Dockerfile
├── docker-compose.yaml
├── Makefile
├── pyproject.toml
├── start_server.sh
├── start_worker.sh
├── start_redis.sh
└── stopAll.sh
```

## Getting Started

### Prerequisites

- Python ≥ 3.10, < 3.14
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker & Docker Compose (for Redis)
- Supabase CLI (for local database & migrations)

### Installation

```bash
cd server
poetry install
```

### Environment Variables

Create a `.env` file in the `server/` directory:

```env
# Supabase
SUPABASE_API_URL=http://127.0.0.1:54321          # or cloud URL
SUPABASE_SERVICE_KEY=your_supabase_service_key

# Clerk
CLERK_SECRET_KEY=sk_test_...
DOMAIN=http://localhost:3000

# S3-Compatible Storage (Tigris)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_ENDPOINT_URL_S3=https://t3.storage.dev
AWS_ENDPOINT_URL_IAM=https://iam.storage.dev
AWS_REGION=auto
S3_BUCKET_NAME=your_bucket_name

# OpenAI
OPENAI_API_KEY=sk-proj-...

# ScrapingBee
SCRAPINGBEE_API_KEY=your_scrapingbee_key

# Redis
REDIS_URL=redis://localhost:6379/0                # or redis://redis:6379/0 for Docker

# LangSmith (optional)
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=DocMind

# Tavily (for web search agent)
TAVILY_API_KEY=your_tavily_key
```

### Database Setup

```bash
# Start local Supabase
supabase start

# Run migrations (creates tables + pgvector search functions)
supabase db push
```

For cloud Supabase, run the migration SQL files in the Supabase SQL Editor.

### Running Locally

You need **4 separate processes** running:

```bash
# Terminal 1 — Redis (via Docker Compose)
make redis
# or: docker compose up redis

# Terminal 2 — FastAPI server
make server
# or: poetry run uvicorn src.server:app --reload --port 8000

# Terminal 3 — Celery worker
make worker
# or: poetry run celery -A src.services.celery:celery_app worker --loglevel=info --pool=threads
```

### Running with Docker Compose (all services)

```bash
docker build -t docmind:1.0.0 .
docker compose up
```

This starts Redis, the FastAPI server (port 8000), and the Celery worker together.

## API Endpoints

| Prefix | Router | Description |
|---|---|---|
| `/api/user` | `userRoutes` | User creation (Clerk webhook) |
| `/api/projects` | `projectRoutes` | Project CRUD, settings, chat messages (streaming) |
| `/api/projects` | `projectFilesRoutes` | File upload (pre-signed URL), URL ingestion, document management |
| `/api/chats` | `chatRoutes` | Chat CRUD |
| `/health` | — | Health check |

## RAG Pipeline

### Ingestion
1. Upload document to S3 via pre-signed URL (or submit a website URL)
2. Celery worker downloads and partitions content using `unstructured`
3. Chunks elements by title, summarizes image/table chunks with LLM
4. Generates vector embeddings (`text-embedding-3-small`) and stores in Supabase (pgvector)

### Retrieval Strategies
- **Basic** — Vector search only
- **Hybrid** — Vector + keyword search with RRF fusion
- **Multi-query Vector** — LLM-generated query variations + RRF fusion
- **Multi-query Hybrid** — Query variations with hybrid search + RRF fusion

## Multi-Agent Architecture

Uses a **LangGraph Supervisor** pattern:
- **Supervisor Agent** — Routes queries to the appropriate sub-agent
- **RAG Sub-Agent** — Searches project documents using the retrieval pipeline
- **Web Search Sub-Agent** — Queries the internet via Tavily / DuckDuckGo

## Guardrails

Input guardrails using an LLM-as-a-Judge (`gpt-4o-mini`) to detect:
- Prompt injection attempts
- PII (Personal Identifiable Information) leakage
- Toxic or harmful content

## Evaluation

```bash
# Collect RAG data
make eval-collect

# Run RAGAS evaluation
make eval-run

# Both steps
make eval-full
```

Evaluates using RAGAS metrics: Context Precision, Context Recall, Faithfulness, and Answer Relevancy.

## Deployment

- **Backend:** AWS ECS Fargate (separate task definitions for API & Worker)
- **Redis:** AWS ElastiCache
- **Load Balancer:** Application Load Balancer (ALB) for FastAPI
- **HTTPS:** CloudFront distribution
- **Container Registry:** AWS ECR
- **Database:** Supabase Cloud
- **Frontend:** Vercel
