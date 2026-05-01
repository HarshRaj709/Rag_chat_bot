from rest_framework import serializers

class ChatSerializer(serializers.Serializer):
    message = serializers.CharField()
    response = serializers.CharField(read_only=True)