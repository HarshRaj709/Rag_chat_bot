# knowledge_base/tasks.py
"""Background ingestion / vector-cleanup jobs.

Request cycle only persists the uploaded file + a `pending` KBDocument row and
enqueues `ingest_document_task`. The worker does extract -> embed -> upsert,
then flips the row to `ready` / `failed`. FE polls the document endpoint.
"""
from __future__ import annotations

import logging
import os

from celery import shared_task
from django.core.files.storage import default_storage
from django.utils import timezone

logger = logging.getLogger(__name__)

# Retry only transient infra errors (embedding / Qdrant / Redis). 
# Bad files (ValueError from extract_text / empty chunks) fail fast with no retry.
RETRYABLE_MARKERS = ("timeout", "temporar", "connection", "unavailable", "rate limit", "429", "503", "502")


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ValueError):
        return False
    msg = str(exc).lower()
    return any(m in msg for m in RETRYABLE_MARKERS)


@shared_task(
    bind=True,
    name="knowledge_base.ingest_document",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def ingest_document_task(self, document_id: str) -> dict:
    from knowledge_base.models import KBDocument
    from knowledge_base.utils import extract_text

    try:
        document = KBDocument.objects.select_related("kb").get(pk=document_id)
    except KBDocument.DoesNotExist:
        logger.warning("ingest_document_task: document %s gone, skipping", document_id)
        return {"ok": False, "reason": "document-not-found"}

    if document.status == KBDocument.STATUS_READY:
        return {"ok": True, "reason": "already-ready", "chunks": document.chunk_count}

    # Don't infinite-retry a poison file: ValueError path marks failed below
    # and we abort retries explicitly.
    document.status = KBDocument.STATUS_PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])

    try:
        if not document.storage_path or not default_storage.exists(document.storage_path):
            raise ValueError("Uploaded file is missing from storage; re-upload the document.")

        with default_storage.open(document.storage_path, "rb") as fh:
            content = fh.read()

        text = extract_text(content, document.filename)

        # Sync service: no event loop involved at all, so the
        # "Event loop is closed" bug class cannot happen. Fresh instance per
        # task + explicit close = no cross-task connection reuse.
        from common.rag_sync import SyncRAGIngestService

        service = SyncRAGIngestService()
        try:
            chunk_count = service.ingest(document.kb, document, text)
        finally:
            service.close()

        document.chunk_count = chunk_count
        document.status = KBDocument.STATUS_READY
        document.ingested_at = timezone.now()
        document.save(update_fields=["chunk_count", "status", "ingested_at", "updated_at"])
        logger.info("Ingested document %s (%d chunks)", document_id, chunk_count)
        return {"ok": True, "chunks": chunk_count}

    except Exception as exc:  # noqa: BLE001 - must persist failure for FE polling
        if isinstance(exc, ValueError) or not _is_retryable(exc):
            # Permanent failure: surface to FE, do NOT retry.
            document.status = KBDocument.STATUS_FAILED
            document.error_message = str(exc)[:2000]
            document.save(update_fields=["status", "error_message", "updated_at"])
            logger.exception("Ingestion failed (permanent) for document %s", document_id)
            return {"ok": False, "reason": str(exc)[:500]}
        # Transient: let Celery retry with backoff (re-raises).
        logger.warning("Ingestion transient failure for %s, retrying: %s", document_id, exc)
        raise


@shared_task(name="knowledge_base.delete_document_vectors", acks_late=True, max_retries=5,
             autoretry_for=(Exception,), retry_backoff=30, retry_backoff_max=300)
def delete_document_vectors_task(collection: str, document_id: str) -> dict:
    """Best-effort vector cleanup after the DB row is gone (fire-and-forget)."""
    from common.rag_sync import SyncRAGIngestService
    from knowledge_base.models import KnowledgeBase

    kb = KnowledgeBase(qdrant_collection=collection)  # lightweight stand-in, no DB hit
    service = SyncRAGIngestService()
    try:
        service.delete_document_vectors(kb, str(document_id))
    finally:
        service.close()
    return {"ok": True}


@shared_task(name="knowledge_base.delete_collection", acks_late=True, max_retries=5,
             autoretry_for=(Exception,), retry_backoff=30, retry_backoff_max=300)
def delete_collection_task(collection: str) -> dict:
    """Best-effort collection cleanup after the KB row is gone."""
    from common.rag_sync import SyncRAGIngestService

    service = SyncRAGIngestService()
    try:
        service.delete_collection(collection)
    finally:
        service.close()
    return {"ok": True}


def document_storage_path(document_id, filename: str) -> str:
    safe_name = os.path.basename(filename).replace(" ", "_")
    return f"kb_docs/{document_id}_{safe_name}"
