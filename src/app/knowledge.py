from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from langchain_openai import OpenAIEmbeddings
from psycopg.types.json import Jsonb

from app.config import settings


def _vector(value: list[float]) -> str:
    return "[" + ",".join(format(item, ".9g") for item in value) + "]"


class KnowledgeStore:
    def __init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", settings.vector_table):
            raise ValueError("VECTOR_TABLE must be a valid PostgreSQL identifier")
        self._embedding_model = OpenAIEmbeddings(
            api_key=settings.dashscope_api_key or "EMPTY",
            base_url=settings.qwen_base_url,
            model=settings.qwen_embedding_model,
            dimensions=settings.qwen_embedding_dimensions,
        )

    def _connect(self):
        return psycopg.connect(
            host=settings.pgvector_host,
            port=settings.pgvector_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        )

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                f"""CREATE TABLE IF NOT EXISTS "{settings.vector_table}" (
                    id UUID PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding vector({settings.qwen_embedding_dimensions}) NOT NULL
                )"""
            )
            conn.commit()

    def embed(self, text: str) -> list[float]:
        return self._embedding_model.embed_query(text)

    def add(self, content: str, metadata: dict) -> dict:
        safe_metadata = dict(metadata)
        safe_metadata["createdAt"] = datetime.now(UTC).isoformat()
        doc_id = str(uuid4())
        embedding = self.embed(content)
        with self._connect() as conn:
            conn.execute(
                f'INSERT INTO "{settings.vector_table}" (id, content, metadata, embedding) '
                "VALUES (%s, %s, %s, %s::vector)",
                (doc_id, content, Jsonb(safe_metadata), _vector(embedding)),
            )
            conn.commit()
        return {"id": doc_id, "content": content, "metadata": safe_metadata, "score": None}

    def search(self, query: str, top_k: int, threshold: float) -> list[dict]:
        embedding = self.embed(query)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT id::text, content, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM "{settings.vector_table}"
                    WHERE 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s""",
                (_vector(embedding), _vector(embedding), threshold, _vector(embedding), top_k),
            ).fetchall()
        return [{"id": row[0], "content": row[1], "metadata": row[2], "score": float(row[3])}
                for row in rows]

    def list(self, keyword: str, page: int, size: int) -> dict:
        pattern = f"%{keyword.strip()}%"
        where = "WHERE content ILIKE %s OR COALESCE(metadata->>'source', '') ILIKE %s" if keyword.strip() else ""
        args = (pattern, pattern) if keyword.strip() else ()
        with self._connect() as conn:
            total = conn.execute(
                f'SELECT COUNT(*) FROM "{settings.vector_table}" {where}', args
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT id::text, content, metadata FROM "{settings.vector_table}" {where}
                    ORDER BY COALESCE(metadata->>'updatedAt', metadata->>'createdAt') DESC NULLS LAST, id DESC
                    LIMIT %s OFFSET %s""",
                (*args, size, page * size),
            ).fetchall()
        return {
            "items": [{"id": row[0], "content": row[1], "metadata": row[2], "score": None} for row in rows],
            "page": page, "size": size, "totalElements": total,
            "totalPages": (total + size - 1) // size,
        }

    def get(self, doc_id: UUID | str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f'SELECT id::text, content, metadata FROM "{settings.vector_table}" WHERE id::text = %s',
                (str(doc_id),),
            ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "content": row[1], "metadata": row[2], "score": None}

    def update(self, doc_id: UUID | str, content: str, metadata: dict) -> dict | None:
        existing = self.get(doc_id)
        if existing is None:
            return None
        merged = dict(existing["metadata"])
        for key, value in metadata.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                merged.pop(key, None)
            else:
                merged[key] = value
        merged.setdefault("createdAt", datetime.now(UTC).isoformat())
        merged["updatedAt"] = datetime.now(UTC).isoformat()
        embedding = self.embed(content)
        with self._connect() as conn:
            conn.execute(
                f'UPDATE "{settings.vector_table}" SET content=%s, metadata=%s, embedding=%s::vector '
                "WHERE id::text=%s",
                (content, Jsonb(merged), _vector(embedding), str(doc_id)),
            )
            conn.commit()
        return {"id": str(doc_id), "content": content, "metadata": merged, "score": None}

    def delete(self, doc_id: UUID | str) -> None:
        with self._connect() as conn:
            conn.execute(f'DELETE FROM "{settings.vector_table}" WHERE id::text=%s', (str(doc_id),))
            conn.commit()

    @staticmethod
    def context(documents: list[dict]) -> str:
        return "\n\n".join(
            f"[来源: {json.dumps(item['metadata'], ensure_ascii=False)}]\n{item['content']}"
            for item in documents
        )
