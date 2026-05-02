import os
from rest_framework import serializers
from knowledge_base.models import KnowledgeBase, KBDocument
from user.models import User

class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model= KnowledgeBase
        fields = ['id', 'name']

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
    

class KBDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KBDocument
        fields = ("id", "filename", "chunk_count", "storage_path",  "ingested_at", "created_at")
        read_only_fields = fields

class KBDetailSerializer(serializers.ModelSerializer):
    documents = KBDocumentSerializer(many=True, read_only=True)
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBase
        fields = ("id", "name", "qdrant_collection", "document_count", "documents", "created_at", "updated_at")
        read_only_fields = fields

    def get_document_count(self, obj):
        return obj.documents.count()


class KBIngestSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        allowed_extensions = [".pdf", ".txt", ".docx"]
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_extensions)}"
            )

        max_size = 20 * 1024 * 1024   #20mb max
        if value.size > max_size:
            raise serializers.ValidationError("File size must be under 20MB.")

        return value