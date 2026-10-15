# Python AI Demo

Python port of the Java Spring AI demo: Qwen chat, LangChain/LangGraph agent orchestration, an independent GIS MCP server, PGVector-backed RAG, and the original static chat/knowledge pages.

## Architecture

```text
Browser (reused HTML/CSS/JS)
        │ REST + SSE
        ▼
FastAPI Agent ── LangGraph + LangChain ── Qwen OpenAI-compatible API
        │                     │
        │ MCP client          └── embeddings + pgvector similarity search
        ▼
Python MCP Server ── calculation and GIS demo tools
        │
        ▼
PostgreSQL + pgvector (Docker Compose)
```

The GIS tools use demonstration records, not live utility systems. The agent must ask the user to choose when a tool returns multiple candidates; the frontend executes only `COMPLETED` map actions.

## Requirements

- Python 3.11+
- Docker Desktop / Docker Compose
- A DashScope API key for Qwen chat and embeddings

## Setup

```powershell
cd python-ai-demo
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `DASHSCOPE_API_KEY` in the process environment or in your local, untracked `.env`. Never commit API keys.

Start the database and MCP server in separate terminals:

```powershell
docker compose -f docker\docker-compose.yml up -d
python -m app.mcp_server
```

Start FastAPI in another terminal:

```powershell
$env:PYTHONPATH = "src"
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open [http://localhost:8080](http://localhost:8080). OpenAPI is available at `/docs`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DASHSCOPE_API_KEY` | empty | DashScope API key; required for agent startup |
| `QWEN_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | OpenAI-compatible endpoint |
| `QWEN_MODEL` | `qwen3.7-plus` | Chat/tool-calling model |
| `QWEN_EMBEDDING_MODEL` | `text-embedding-v4` | Embedding model |
| `QWEN_EMBEDDING_DIMENSIONS` | `1024` | PGVector dimension |
| `MCP_SERVER_URL` | `http://localhost:8081` | MCP server base URL |
| `PGVECTOR_HOST` | `localhost` | PostgreSQL host |
| `PGVECTOR_PORT` | `5556` | Host port (separate from the Java demo's default port) |
| `VECTOR_TABLE` | `python_vector_store` | Python app's vector table (separate from the Java demo table) |

The Python port uses a separate `python_vector_store` table by default so its embedding configuration cannot overwrite or conflict with Java data. The table dimension is fixed when first created; changing the embedding dimension requires a new table or an explicit migration.

## API compatibility

- `POST /api/chat`: accepts `conversationId` and `message`; returns `content` and `toolResults`.
- `POST /api/chat/stream`: emits `tool`, `token`, `done` and `error` SSE events. As in the current Java implementation, the completed answer is sent in one `token` event.
- Knowledge endpoints: `POST /api/knowledge/documents`, `GET /api/knowledge/documents`, `GET /api/knowledge/documents/{id}`, `PUT /api/knowledge/documents/{id}`, `POST /api/knowledge/search`, `DELETE /api/knowledge/documents/{id}`.
- Chat messages are limited to 4,000 characters. Conversation history is held in process memory, capped at 20 messages per conversation, and cleared on restart.
- Knowledge text is limited to 20,000 characters.
- Knowledge pagination returns `items`, `page`, `size`, `totalElements`, and `totalPages`.

## MCP tools

`calculate`, `locateEquipment`, `viewHostedLayer`, `drawGeometryRegion`, `browseConstructionProject`.
The MCP server exposes Streamable HTTP at `http://localhost:8081/mcp`.

## Development

```powershell
pytest
ruff check src tests
```

All GIS fixtures are demonstration data and do not represent live grid assets or project records.
