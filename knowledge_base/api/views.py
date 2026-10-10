from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.mixins import GetOrgMixin
from common.permissions import IsOrgAdmin, IsOrgMember
from knowledge_base.models import KBDocument, KnowledgeBase
from knowledge_base.tasks import (
    delete_collection_task,
    delete_document_vectors_task,
    document_storage_path,
    ingest_document_task,
)

from .serializers import (
    KBDetailSerializer,
    KBDocumentSerializer,
    KBIngestSerializer,
    KnowledgeBaseSerializer,
)


class KBListCreateView(GetOrgMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KnowledgeBaseSerializer

    def get_permissions(self):
        # members can list, only admin/owner can create
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOrgMember(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]

    def get_serializer_context(self):  
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_queryset(self):
        return KnowledgeBase.objects.filter(org=self.get_org()).annotate(
            annotated_document_count=Count("documents", distinct=True),
            annotated_chunks_count=Coalesce(Sum("documents__chunk_count"), Value(0)),
        ).order_by("-created_at")
    

class KBDetailView(GetOrgMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBDetailSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_permissions(self):
        # members can view/update, only admin/owner can delete
        if self.request.method == "DELETE":
            return [IsAuthenticated(), IsOrgMember(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]

    def get_serializer_context(self):
        context =  super().get_serializer_context()
        context['org'] = self.get_org()
        return context
    
    def get_object(self):
        return get_object_or_404(
            KnowledgeBase.objects.select_related("org").annotate(
                annotated_document_count=Count("documents", distinct=True),
                annotated_chunks_count=Coalesce(Sum("documents__chunk_count"), Value(0)),
            ).prefetch_related("documents"),
            pk=self.kwargs["kb_pk"],
            org=self.get_org()
        )
    
    def perform_destroy(self, instance):
        # Delete the DB row now; vector cleanup is best-effort background work
        # so a slow Qdrant call never blocks the response.
        collection = instance.qdrant_collection
        instance.delete()
        transaction.on_commit(lambda: delete_collection_task.delay(collection))


class KBDocumentDetailView(GetOrgMixin, GenericAPIView):
    """Polling endpoint for FE: GET -> {status: pending|processing|ready|failed}.

    Also handles DELETE (same path as before — backward compatible).
    """
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBDocumentSerializer

    def get_object(self):
        # Single query (JOIN on kb__org) instead of one for the KB + one
        # for the document.
        return get_object_or_404(
            KBDocument.objects.select_related("kb"),
            pk=self.kwargs["doc_pk"],
            kb__pk=self.kwargs["kb_pk"],
            kb__org=self.get_org(),
        )

    def get(self, request, *args, **kwargs):
        return Response(KBDocumentSerializer(self.get_object()).data)

    def delete(self, request, *args, **kwargs):
        document = self.get_object()

        collection = document.kb.qdrant_collection
        doc_id = str(document.id)
        storage_path = document.storage_path
        document.delete()

        if storage_path and default_storage.exists(storage_path):
            default_storage.delete(storage_path)
        # Best-effort: row is already gone, vectors cleaned async.
        transaction.on_commit(
            lambda: delete_document_vectors_task.delay(collection, doc_id)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class KBDocumentDeleteView(KBDocumentDetailView):
    """Backward-compat alias (DELETE only usage)."""
    http_method_names = ["delete", "options", "head"]


class KBIngestView(GetOrgMixin, GenericAPIView):
    """Enqueue ingestion, return 202 immediately. FE polls document status."""
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBIngestSerializer

    def post(self, request, *args, **kwargs):
        org = self.get_org()
        kb = get_object_or_404(KnowledgeBase, pk=self.kwargs["kb_pk"], org=org)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        content = uploaded_file.read()  # 20MB max enforced by serializer
        if not content:
            return Response({"error": "Uploaded file is empty."}, status=status.HTTP_400_BAD_REQUEST)

        document = KBDocument.objects.create(
            kb=kb,
            filename=uploaded_file.name,
            storage_path="",
            file_size=uploaded_file.size,
            status=KBDocument.STATUS_PENDING,
        )
        storage_path = document_storage_path(document.id, uploaded_file.name)
        default_storage.save(storage_path, ContentFile(content))
        document.storage_path = storage_path
        document.save(update_fields=["storage_path", "updated_at"])

        # Enqueue only after commit so the worker always sees the row.
        transaction.on_commit(lambda: ingest_document_task.delay(str(document.id)))

        return Response(
            KBDocumentSerializer(document).data,
            status=status.HTTP_202_ACCEPTED,
        )


class KBDocumentRetryView(GetOrgMixin, GenericAPIView):
    """Re-enqueue a failed document: POST -> 202 {status: pending}."""
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBDocumentSerializer

    def post(self, request, *args, **kwargs):
        document = get_object_or_404(
            KBDocument,
            pk=self.kwargs["doc_pk"],
            kb__pk=self.kwargs["kb_pk"],
            kb__org=self.get_org(),
        )

        if document.status in (KBDocument.STATUS_PENDING, KBDocument.STATUS_PROCESSING):
            return Response(
                {"detail": f"Document is already {document.status}; poll its status."},
                status=status.HTTP_409_CONFLICT,
            )

        document.status = KBDocument.STATUS_PENDING
        document.error_message = ""
        document.save(update_fields=["status", "error_message", "updated_at"])
        transaction.on_commit(lambda: ingest_document_task.delay(str(document.id)))
        return Response(KBDocumentSerializer(document).data, status=status.HTTP_202_ACCEPTED)
