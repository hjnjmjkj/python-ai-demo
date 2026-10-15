import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class FakeKnowledgeStore:
    def search(self, query, top_k, threshold):
        return []

    @staticmethod
    def context(documents):
        return ""


class FakeAgent:
    async def chat(self, conversation_id, message, knowledge_context):
        return {
            "content": f"已收到：{message}",
            "toolResults": [{
                "toolName": "calculate",
                "arguments": {"left": 1, "right": 2},
                "result": {"result": 3},
            }],
        }


@pytest.mark.asyncio
async def test_health_and_reused_static_pages():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/health")
        index = await client.get("/")
        knowledge_page = await client.get("/knowledge.html")
        stylesheet = await client.get("/styles.css")

    assert health.status_code == 200
    assert health.json() == {"status": "UP"}
    assert index.status_code == 200
    assert "Qwen RAG" in index.text
    assert knowledge_page.status_code == 200
    assert stylesheet.status_code == 200


@pytest.mark.asyncio
async def test_chat_response_and_sse_contract():
    app.state.agent = FakeAgent()
    app.state.knowledge = FakeKnowledgeStore()
    payload = {
        "conversationId": "7f3ad908-937f-4d5f-b4d1-fd5aef7d44a1",
        "message": "计算 1+2",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/chat", json=payload)
        stream = await client.post("/api/chat/stream", json=payload)

    assert response.status_code == 200
    assert response.json()["content"] == "已收到：计算 1+2"
    assert response.json()["toolResults"][0]["result"] == {"result": 3}
    assert "event: tool" in stream.text
    assert "event: token" in stream.text
    assert "event: done" in stream.text
    assert stream.text.index("event: tool") < stream.text.index("event: token") < stream.text.index("event: done")
