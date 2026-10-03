import os

from django.db.models import Sum
from rest_framework import serializers
from knowledge_base.models import KnowledgeBase, KBDocument
from user.models import User

class KnowledgeBaseSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField(read_only=True)
    chunks_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model= KnowledgeBase
        fields = ['id', 'name', 'description', 'document_count', 'chunks_count']
        read_only_fields = ('id', 'document_count', 'chunks_count')

    def validate_name(self, value):
        org = self.context['org']
        if not org:
            raise serializers.ValidationError("Organization context is required.")
        qs = KnowledgeBase.objects.filter(name__iexact=value, org=org)

        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("This name is already used")
        return value
    
    def create(self, validated_data):
        return KnowledgeBase.objects.create(org=self.context['org'], **validated_data)

    def get_document_count(self, obj):
        # Prefers the annotated value from the list queryset (no extra query);
        # falls back to a query for single-object responses (e.g. just created).
        if hasattr(obj, "annotated_document_count"):
            return obj.annotated_document_count
        return obj.documents.count()

    def get_chunks_count(self, obj):
        if hasattr(obj, "annotated_chunks_count"):
            return obj.annotated_chunks_count or 0
        return obj.documents.aggregate(total=Sum("chunk_count"))["total"] or 0
    

class KBDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KBDocument
        fields = ("id", "filename", "file_size", "status", "error_message", "chunk_count", "storage_path", "ingested_at", "created_at")
        read_only_fields = fields

class KBDetailSerializer(serializers.ModelSerializer):
    documents = KBDocumentSerializer(many=True, read_only=True)
    document_count = serializers.SerializerMethodField()
    chunks_count = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBase
        fields = ("id", "name", "description", "qdrant_collection", "document_count", "chunks_count", "documents", "created_at", "updated_at")
        read_only_fields = ("id", "qdrant_collection", "document_count", "chunks_count", "documents", "created_at", "updated_at")

    def get_document_count(self, obj):
        if hasattr(obj, "annotated_document_count"):
            return obj.annotated_document_count
        return obj.documents.count()

    def get_chunks_count(self, obj):
        if hasattr(obj, "annotated_chunks_count"):
            return obj.annotated_chunks_count or 0
        return obj.documents.aggregate(total=Sum("chunk_count"))["total"] or 0


class KBIngestSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        allowed_extensions = [".pdf", ".txt", ".md", ".docx"]
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_extensions)}"
            )

        max_size = 20 * 1024 * 1024   #20mb max
        if value.size > max_size:
            raise serializers.ValidationError("File size must be under 20MB.")

        return value