from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.agent import AgentService
from app.config import settings
from app.knowledge import KnowledgeStore
from app.schemas import ChatRequest, ChatResponse, KnowledgeAddRequest, KnowledgeSearchRequest

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent = AgentService()
    knowledge = KnowledgeStore()
    knowledge.initialize()
    await agent.initialize()
    app.state.agent = agent
    app.state.knowledge = knowledge
    yield


app = FastAPI(title="Qwen GIS Agent (Python)", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "UP"}


def _services(request: Request):
    return request.app.state.agent, request.app.state.knowledge


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    agent, knowledge = _services(request)
    try:
        docs = knowledge.search(payload.message, top_k=5, threshold=0.65)
        result = await agent.chat(str(payload.conversationId), payload.message, knowledge.context(docs))
        return {"conversationId": payload.conversationId, **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="智能助手暂时无法完成请求，请确认 Qwen、MCP 和 PostgreSQL 均可用后重试。") from exc


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request):
    agent, knowledge = _services(request)

    async def events() -> AsyncIterator[str]:
        try:
            docs = knowledge.search(payload.message, top_k=5, threshold=0.65)
            result = await agent.chat(str(payload.conversationId), payload.message, knowledge.context(docs))
            for tool in result["toolResults"]:
                yield f"event: tool\ndata: {json.dumps(tool, ensure_ascii=False)}\n\n"
            yield f"event: token\ndata: {json.dumps({'content': result['content']}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {\"content\":\"\"}\n\n"
        except Exception:
            logger.exception("Streaming chat failed")
            yield f"event: error\ndata: {json.dumps({'content': '智能助手暂时无法完成请求，请确认 Qwen、MCP 和 PostgreSQL 均可用后重试。'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/knowledge/documents", status_code=201)
def add_knowledge(payload: KnowledgeAddRequest, request: Request):
    if len(payload.content) > settings.max_document_chars:
        raise HTTPException(status_code=422, detail="知识文本最多 20000 字符")
    try:
        return request.app.state.knowledge.add(payload.content, payload.metadata or {})
    except Exception as exc:
        raise HTTPException(status_code=502, detail="知识入库失败，请检查向量模型和 PostgreSQL 连接") from exc


@app.get("/api/knowledge/documents")
def list_knowledge(
    request: Request,
    page: int = Query(default=0, ge=0),
    size: int = Query(default=10, ge=1, le=100),
    keyword: str = "",
):
    try:
        return request.app.state.knowledge.list(keyword, page, size)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="读取知识库失败，请检查 PostgreSQL 连接") from exc


@app.get("/api/knowledge/documents/{doc_id}")
def get_knowledge(doc_id: UUID, request: Request):
    try:
        result = request.app.state.knowledge.get(doc_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="读取知识详情失败") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="知识不存在")
    return result


@app.put("/api/knowledge/documents/{doc_id}")
def update_knowledge(doc_id: UUID, payload: KnowledgeAddRequest, request: Request):
    try:
        result = request.app.state.knowledge.update(doc_id, payload.content, payload.metadata or {})
    except Exception as exc:
        raise HTTPException(status_code=502, detail="更新知识失败，请检查向量模型和 PostgreSQL 连接") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="知识不存在")
    return result


@app.post("/api/knowledge/search")
def search_knowledge(payload: KnowledgeSearchRequest, request: Request):
    try:
        return request.app.state.knowledge.search(
            payload.query,
            payload.topK or 5,
            payload.similarityThreshold if payload.similarityThreshold is not None else 0.65,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="知识检索失败，请检查向量模型和 PostgreSQL 连接") from exc


@app.delete("/api/knowledge/documents/{doc_id}", status_code=204)
def delete_knowledge(doc_id: UUID, request: Request):
    try:
        request.app.state.knowledge.delete(doc_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="删除知识失败") from exc


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
