from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView, DestroyAPIView, GenericAPIView
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsOrgAdmin, IsOrgMember
from knowledge_base.models import KnowledgeBase, KBDocument
from organization.models import Organisation
from .serializers import KnowledgeBaseSerializer, KBDetailSerializer, KBIngestSerializer
from django.shortcuts import get_object_or_404
from rest_framework import status
from knowledge_base.rag import rag_service


class KBListCreateView(ListCreateAPIView):
    """
    GET  /orgs/{pk}/kbs/    → list all KBs in this org
    POST /orgs/{pk}/kbs/    → create a new KB
    Any org member can do both.
    """
    permission_classes = [IsAuthenticated, IsOrgMember, IsOrgAdmin]
    serializer_class = KnowledgeBaseSerializer

    def get_org(self):      #cache
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org

    def get_serializer_context(self):           #used to add org in serializer
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_queryset(self):
        return KnowledgeBase.objects.filter(org=self.get_org())
    

class KBDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBDetailSerializer
    http_method_names = ["get", "patch", "delete"]


    def get_org(self):
        if not hasattr(self, '_org'):
            self._org = get_object_or_404(Organisation, id=self.kwargs['pk'])
        return self._org
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return KnowledgeBaseSerializer
        return KBDetailSerializer

    def get_parser_context(self, http_request):
        context =  super().get_parser_context()
        context['org'] = self.kwargs['pk']
        return context
    
    def get_object(self):
        return get_object_or_404(
            KnowledgeBase,
            pk=self.kwargs["kb_pk"],
            org=self.get_org()
        )
    
    def perform_destroy(self, instance):
        # hard delete Qdrant collection first, then the DB row
        rag_service.delete_collection(instance.qdrant_collection)
        instance.delete()
    
class KBDocumentDeleteView(GenericAPIView):
    """
    DELETE /orgs/{pk}/kbs/{kb_pk}/documents/{doc_pk}/
    Remove a document's vectors from Qdrant and delete the DB row.
    """
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_org(self):
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org
    
    def delete(self, request, *args, **kwargs):
            org = self.get_org()
            kb = get_object_or_404(KnowledgeBase, pk=self.kwargs["kb_pk"], org=org)
            document = get_object_or_404(KBDocument, pk=self.kwargs["doc_pk"], kb=kb)

            # delete vectors from Qdrant first
            try:
                rag_service.delete_document_vectors(kb, str(document.id))
            except Exception as e:
                return Response(
                    {"error": f"Failed to delete vectors: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            document.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
    

class KBIngestView(GenericAPIView):
    """
    POST /orgs/{pk}/kbs/{kb_pk}/ingest/
    Upload a file → extract text → chunk → embed → store in Qdrant
    """
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBIngestSerializer

    def get_org(self):
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org

    def post(self, request, *args, **kwargs):
        org = self.get_org()
        kb = get_object_or_404(KnowledgeBase, pk=self.kwargs["kb_pk"], org=org)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        content = uploaded_file.read()

        # extract text based on file type
        try:
            text = extract_text(content, uploaded_file.name)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # create document record first — so we have an ID for vector payloads
        document = KBDocument.objects.create(
            kb=kb,
            original_filename=uploaded_file.name,
            storage_path="",        # update below after storage upload
            chunk_count=0,          # update below after ingestion
        )
        try:
            chunk_count = rag_service.ingest(kb, document, text)
        except Exception as e:
            document.delete()       # clean up DB row if Qdrant fails
            return Response({"error": f"Ingestion failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # update document record with final chunk count and timestamp
        document.chunk_count = chunk_count
        document.ingested_at = timezone.now()
        document.save(update_fields=["chunk_count", "ingested_at"]) #partial update

        return Response(
            KBDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED
        )