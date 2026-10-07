# DocMind Server - Agent Engineering Instructions

This file contains backend-specific instructions for agents working in the `server/` directory. For project-wide rules, refer to the root `AGENTS.md`.

## 1. Backend Engineering Conventions
- **Language/Package Manager**: Python 3.12 managed via Poetry.
- **Logging**: Use `structlog` via `src.config.logging.get_logger`. Do **NOT** use `print()`. Ensure contextvars (`request_id`, `user_id`, `project_id`) are maintained.
- **Routing**: FastAPI. All routes must be registered in `src/server.py`.
- **Async Tasks**: Document ingestion runs asynchronously via Celery (thread pool, not prefork). Do not introduce new async dependencies unless necessary.
- **File System**: Avoid hardcoding temporary paths. Ingestion uses `/tmp/{document_id}.{ext}`.

## 2. RAG/Retrieval-Specific Rules
- **Embeddings**: `text-embedding-3-small` (1536 dimensions). Hardcoded in DB schema `vector(1536)`.
- **Retrieval Strategies**: Must support `basic`, `hybrid`, `multi-query-vector`, `multi-query-hybrid`.
- **Fusion**: Use Reciprocal Rank Fusion (RRF) when combining vector/keyword results or multi-query results.
- **Ingestion**: Generate AI summaries only for chunks containing tables or images to manage costs.

## 3. LangGraph/Agent-Related Rules
- **Guardrails**: All user inputs must pass the `guardrail_node` (LLM-as-a-judge for toxicity/PII) before reaching agents.
- **Citation Propagation**: Ensure citations propagate through the graph state (`lambda x, y: x + y` reducer).
- **Supervisor Rules**: `supervisor_agent` routing prioritizes `rag_search` before `search_web`. Do not answer factual questions directly if tool usage is required.

## 4. Database and Data-Access Rules
- **Client**: Use the Supabase Python SDK directly. Do **NOT** introduce an ORM.
- **Authorization**: Enforce data isolation manually by appending `.eq("clerk_id", current_user_clerk_id)` to ALL queries.
- **Search**: Use existing RPC functions (`vector_search_document_chunks`, `keyword_search_document_chunks`).
- **Transactions**: Rely on sequential inserts. Avoid complex transactions unless necessary.

## 5. Backend Testing Guidance
Follow the root testing philosophy. The backend currently has zero tests, but when implementing tests, adhere to these rules:

- **Unit Tests (`tests/unit/`)**: 
  - Use `pytest`.
  - Test deterministic application logic directly (e.g., pure functions in `src.rag.ingestion.utils` or `src.rag.retrieval.utils`).
  - Avoid unnecessary mocking for pure functions. Do not test framework behavior. Keep them fast and isolated.
- **API Integration Tests (`tests/integration/`)**: 
  - Test actual route behavior, request validation, responses, and error handling.
  - Mock external services (OpenAI, Clerk) to ensure deterministic API routing behavior. Do not confuse this with database integration.
- **Database Integration Tests (`tests/integration/`)**: 
  - Use a real PostgreSQL/pgvector test environment.
  - Test RPC/query behavior, vector search, and data isolation against the real database schema. Do not rely solely on mocked DB calls.
- **Celery Tests (`tests/integration/`)**: 
  - Test task behavior and state transitions (`perform_rag_ingestion_task`).
  - Mock expensive external processing. Use real queue infrastructure (Redis) when queue behavior itself is being tested.
- **LangGraph/Agent Tests (`tests/integration/`)**: 
  - Test graph state transitions, routing, tool handling, guardrails, stopping conditions, and error paths.
  - Mock LLM responses when testing deterministic workflow behavior. Keep this separate from AI evaluation.

## 6. RAG Evaluation (`rag_evaluation/`)
- Software tests verify implementation behavior; RAG evaluations measure retrieval/generation quality.
- The `rag_evaluation/` directory contains existing scripts (e.g., `ragas_data_collection.py`).
- Run evaluations locally using existing Make targets: `make eval-full` (which runs `eval-collect` and `eval-run`).
- Ensure `Faithfulness` and `AnswerRelevancy` scores do not degrade when changing prompts or retrieval logic.

