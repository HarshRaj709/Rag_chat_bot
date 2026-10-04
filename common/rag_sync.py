# common/rag_sync.py
"""Sync ingestion path for Celery workers.

Why a separate sync service instead of re-using ``common.rag.RAGService``?
Celery tasks are sync. Calling an async service via ``async_to_sync`` re-uses
httpx/Redis pools that were created on a *different* (already closed) event
loop -> ``RuntimeError: Event loop is closed`` (very visible on Windows).

Sync clients (``OpenAI`` / ``QdrantClient``) have no event loop at all, so the
whole bug class disappears. Chunking / point-ids / collection settings are kept
identical to the async path so vectors stay compatible.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 96
UPSERT_BATCH_SIZE = 128
_NAMESPACE = uuid.UUID("6f1c2b0e-3b7a-4a55-9d0f-0c1d5a8f7e11")


def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, name, default)


class SyncRAGIngestService:
    """Short-lived, one instance per Celery task. Create -> use -> close."""

    def __init__(self) -> None:
        self._embed_model = _cfg("RAG_EMBED_MODEL", "text-embedding-3-small")
        self._embed_dim = _cfg("RAG_EMBED_DIM", 1536)
        self.openai = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.BASE_URL,
            timeout=30.0,
            max_retries=3,
        )
        self.qdrant = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=30,
            check_compatibility=False,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=_cfg("RAG_CHUNK_SIZE", 400),
            chunk_overlap=_cfg("RAG_CHUNK_OVERLAP", 40),
        )

    def close(self) -> None:
        try:
            self.openai.close()
        except Exception:
            pass
        try:
            self.qdrant.close()
        except Exception:
            pass

    # -- collections ---------------------------------------------------- #
    def ensure_collection(self, name: str) -> None:
        if not self.qdrant.collection_exists(name):
            try:
                self.qdrant.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=self._embed_dim, distance=Distance.COSINE),
                )
            except UnexpectedResponse as e:  # created concurrently by another worker
                if e.status_code != 409:
                    raise
        # idempotent
        self.qdrant.create_payload_index(
            collection_name=name,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )

    def delete_collection(self, name: str) -> None:
        if self.qdrant.collection_exists(name):
            self.qdrant.delete_collection(collection_name=name)

    # -- embeddings ------------------------------------------------------ #
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            resp = self.openai.embeddings.create(model=self._embed_model, input=batch)
            ordered = sorted(resp.data, key=lambda d: d.index)
            vectors.extend([d.embedding for d in ordered])
        return vectors

    # -- ingestion -------------------------------------------------------- #
    def ingest(self, kb, document, text: str, *, replace: bool = True) -> int:
        """Chunk, embed and upsert. Safe to re-run (deterministic point ids)."""
        self.ensure_collection(kb.qdrant_collection)

        chunks = self.splitter.split_text(text)
        if not chunks:
            raise ValueError("No text content could be extracted from this file.")

        vectors = self.embed_documents(chunks)

        doc_id = str(document.id)
        points = [
            PointStruct(
                id=str(uuid.uuid5(_NAMESPACE, f"{doc_id}:{i}")),
                vector=vec,
                payload={
                    "content": chunk,
                    "document_id": doc_id,
                    "filename": document.filename,
                    "chunk_index": i,
                },
            )
            for i, (chunk, vec) in enumerate(zip(chunks, vectors))
        ]

        if replace:
            self.delete_document_vectors(kb, doc_id)

        for i in range(0, len(points), UPSERT_BATCH_SIZE):
            self.qdrant.upsert(
                collection_name=kb.qdrant_collection,
                points=points[i : i + UPSERT_BATCH_SIZE],
                wait=True,
            )
        return len(points)

    def delete_document_vectors(self, kb, document_id: str) -> None:
        self.qdrant.delete(
            collection_name=kb.qdrant_collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    )
                ]
            ),
            wait=True,
        )
