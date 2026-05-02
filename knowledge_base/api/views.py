from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView, DestroyAPIView, GenericAPIView
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsOrgAdmin, IsOrgMember
from common.mixins import GetOrgMixin
from knowledge_base.models import KnowledgeBase, KBDocument
from organization.models import Organisation
from .serializers import KnowledgeBaseSerializer, KBDetailSerializer, KBIngestSerializer, KBDocumentSerializer
from django.shortcuts import get_object_or_404
from rest_framework import status
from common.rag import rag_service
from knowledge_base.utils import extract_text
from django.utils import timezone


class KBListCreateView(GetOrgMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember, IsOrgAdmin]
    serializer_class = KnowledgeBaseSerializer

    def get_serializer_context(self):  
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_queryset(self):
        return KnowledgeBase.objects.filter(org=self.get_org())
    

class KBDetailView(GetOrgMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBDetailSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_serializer_context(self):
        context =  super().get_serializer_context()
        context['org'] = self.get_org()
        return context
    
    def get_object(self):
        return get_object_or_404(
            KnowledgeBase,
            pk=self.kwargs["kb_pk"],
            org=self.get_org()
        )
    
    def perform_destroy(self, instance):
        rag_service.delete_collection(instance.qdrant_collection)
        instance.delete()
    
class KBDocumentDeleteView(GetOrgMixin, GenericAPIView):
    """
    Single document delete.
    """
    permission_classes = [IsAuthenticated, IsOrgMember]
    
    def delete(self, request, *args, **kwargs):
            org = self.get_org()
            kb = get_object_or_404(KnowledgeBase, pk=self.kwargs["kb_pk"], org=org)
            document = get_object_or_404(KBDocument, pk=self.kwargs["doc_pk"], kb=kb)

            try:
                rag_service.delete_document_vectors(kb, str(document.id))
            except Exception as e:
                return Response(
                    {"error": f"Failed to delete vectors: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            document.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
    

class KBIngestView(GetOrgMixin, GenericAPIView):
    """
    Ingest docs
    """
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = KBIngestSerializer

    def post(self, request, *args, **kwargs):
        org = self.get_org()
        kb = get_object_or_404(KnowledgeBase, pk=self.kwargs["kb_pk"], org=org)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        content = uploaded_file.read()

        try:
            text = extract_text(content, uploaded_file.name)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        #document store first, to get id for vector payloads
        document = KBDocument.objects.create(
            kb=kb,
            filename=uploaded_file.name,
            storage_path="",        
            chunk_count=0,      
        )
        try:
            chunk_count = rag_service.ingest(kb, document, text)
        except Exception as e:
            document.delete()
            return Response({"error": f"Ingestion failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        document.chunk_count = chunk_count
        document.ingested_at = timezone.now()
        document.save(update_fields=["chunk_count", "ingested_at"]) #partial update

        return Response(
            KBDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED
        )