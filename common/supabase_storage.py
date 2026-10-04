"""Supabase Storage backend for Django file uploads.

Replaces local MEDIA_ROOT for KB documents. All existing call sites
(`default_storage.save / open / exists / delete` in
knowledge_base/api/views.py and knowledge_base/tasks.py) keep working
unchanged — only settings.STORAGES switches the backend.

Required env:
    SUPABASE_URL=https://<project-ref>.supabase.co   (NOT the db pooler host)
    SUPABASE_SERVICE_ROLE_KEY=sb_secret_...          (server-side only, never expose)
    SUPABASE_STORAGE_BUCKET=kb-documents
"""
from __future__ import annotations

import io
import logging
import mimetypes

from django.conf import settings
from django.core.files.base import ContentFile, File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)


@deconstructible
class SupabaseStorage(Storage):
    def __init__(self, bucket=None, base_url=None, service_key=None):
        self.bucket_name = (
            bucket or getattr(settings, "SUPABASE_STORAGE_BUCKET", None) or "kb-documents"
        )
        self.base_url = (
            base_url or getattr(settings, "SUPABASE_URL", None) or ""
        ).rstrip("/")
        self.service_key = (
            service_key
            or getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
            or getattr(settings, "SUPABASE_KEY", None)
            or ""
        )
        self._client = None
        if not self.base_url or not self.service_key:
            logger.warning(
                "SupabaseStorage misconfigured: set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY in .env"
            )

    def _get_bucket(self):
        if self._client is None:
            from supabase import create_client

            self._client = create_client(self.base_url, self.service_key)
        return self._client.storage.from_(self.bucket_name)

    def _save(self, name, content):
        name = name.replace("\\", "/")
        data = content.read()
        content_type, _ = mimetypes.guess_type(name)
        bucket = self._get_bucket()
        bucket.upload(
            name,
            data,
            {"content-type": content_type or "application/octet-stream", "upsert": "true"},
        )
        return name

    def _open(self, name, mode="rb"):
        bucket = self._get_bucket()
        data = bucket.download(name)
        fh = ContentFile(data)
        fh.name = name
        # Wrap so callers can use `with default_storage.open(...) as fh:`
        return File(fh, name)

    def exists(self, name):
        try:
            return bool(self._get_bucket().exists(name))
        except Exception:
            logger.exception("SupabaseStorage.exists failed for %s", name)
            return False

    def delete(self, name):
        try:
            self._get_bucket().remove([name])
        except Exception:
            logger.exception("SupabaseStorage.delete failed for %s", name)

    def url(self, name):
        """Signed URL (private bucket) with public-URL fallback."""
        try:
            res = self._get_bucket().create_signed_url(name, 3600)
            signed = res.get("signedURL") if isinstance(res, dict) else None
            if signed:
                if signed.startswith("http"):
                    return signed
                return f"{self.base_url}/storage/v1{signed}"
        except Exception:
            logger.debug("Signed URL failed for %s, falling back to public URL", name)
        try:
            return self._get_bucket().get_public_url(name)
        except Exception:
            return f"{self.base_url}/storage/v1/object/public/{self.bucket_name}/{name}"

    def size(self, name):
        try:
            info = self._get_bucket().info(name)
            if isinstance(info, dict) and info.get("size"):
                return int(info["size"])
        except Exception:
            pass
        # Fallback: download (docs are <=20MB per serializer validation)
        return len(self._get_bucket().download(name))

    def get_available_name(self, name, max_length=None):
        # Paths already contain the document UUID (see document_storage_path),
        # so overwriting with upsert=true is safe and idempotent.
        return name
