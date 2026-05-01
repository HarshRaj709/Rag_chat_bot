from rest_framework import serializers
from knowledge_base.models import KnowledgeBase, KBDocument
from user.models import User

class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model= KnowledgeBase
        fields = ['name']

    def validate_name(self, value):
        org = self.context['org']
        if not org:
            raise serializers.ValidationError("Organization context is required.")
        print("this is context passed", self.context)
        qs = KnowledgeBase.objects.filter(name__iexact=value, org=org)

        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("This name is already used")
        return value
    
    def create(self, validated_data):
        return KnowledgeBase.objects.create(org=self.context['org'], **validated_data)
