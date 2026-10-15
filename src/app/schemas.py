from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    conversationId: UUID
    message: str = Field(min_length=1, max_length=4_000)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class ToolResult(BaseModel):
    toolName: str
    arguments: Any
    result: Any


class ChatResponse(BaseModel):
    conversationId: UUID
    content: str
    toolResults: list[ToolResult]


class KnowledgeAddRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    metadata: dict[str, Any] | None = None

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    topK: int | None = Field(default=5, ge=1, le=20)
    similarityThreshold: float | None = Field(default=0.65, ge=0.0, le=1.0)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class KnowledgeDocument(BaseModel):
    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None


class KnowledgePage(BaseModel):
    items: list[KnowledgeDocument]
    page: int
    size: int
    total: int
    totalPages: int
