from rest_framework import serializers
from chat_bot.models import Bot, BotAPIKey
from knowledge_base.api.serializers import KBDetailSerializer


class BotAPIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = BotAPIKey
        fields = ("id", "name", "prefix", "is_active", "created_at")
        read_only_fields = fields


class BotSerializer(serializers.ModelSerializer):
    """Used for list and create."""
    class Meta:
        model = Bot
        fields = (
            "id", "name", "slug", "system_prompt",
            "temperature", "max_tokens", "is_active",
            "public_url", "created_at", "updated_at"
        )
        read_only_fields = ("id", "slug", "public_url", "created_at", "updated_at")

    def create(self, validated_data):
        org = self.context["org"]
        bot = Bot.objects.create(org=org, **validated_data)
        # auto generate API key on bot creation
        _, raw_key = BotAPIKey.generate(bot, name="default")
        # store raw key temporarily so view can return it once
        bot._raw_api_key = raw_key
        return bot


class BotDetailSerializer(serializers.ModelSerializer):
    """Used for retrieve — includes full KB details and API keys."""
    kbs = KBDetailSerializer(many=True, read_only=True)
    api_keys = BotAPIKeySerializer(many=True, read_only=True)
    kb_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=__import__('knowledge_base.models', fromlist=['KnowledgeBase']).KnowledgeBase.objects.none(),
        source="kbs",
        write_only=True,
        required=False,
    )

    class Meta:
        model = Bot
        fields = (
            "id", "name", "slug", "system_prompt",
            "temperature", "max_tokens", "is_active",
            "public_url", "kbs", "kb_ids", "api_keys",
            "created_at", "updated_at"
        )
        read_only_fields = ("id", "slug", "public_url", "created_at", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        org = self.context.get("org")
        if org:
            from knowledge_base.models import KnowledgeBase
            self.fields["kb_ids"].child_relation.queryset = (
                KnowledgeBase.objects.filter(org=org)
            )

    def validate_temperature(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError("Temperature must be between 0.0 and 1.0.")
        return value

    def validate_max_tokens(self, value):
        if not 64 <= value <= 4096:
            raise serializers.ValidationError("Max tokens must be between 64 and 4096.")
        return value