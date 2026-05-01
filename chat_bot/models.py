from django.db import models
from organization.models import Organisation
from knowledge_base.models import KnowledgeBase
import secrets, hashlib
from common.models import BaseModel

# Create your models here.
class Bot(BaseModel):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="bots")
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    kbs = models.ManyToManyField(KnowledgeBase, related_name="bots", blank=True)
    temperature = models.FloatField(default=0.2)
    max_tokens = models.IntegerField(default=512)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BotAPIKey(BaseModel):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=80)
    prefix = models.CharField(max_length=12)
    key_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate(cls, bot, name="default"):
        raw = "ragbot_live_" + secrets.token_urlsafe(32)
        hashed = hashlib.sha256(raw.encode()).hexdigest()
        obj = cls.objects.create(bot=bot, name=name, prefix=raw[:12], key_hash=hashed)
        return obj, raw

    @classmethod
    def verify(cls, raw_key):
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        return cls.objects.select_related("bot").get(
            key_hash=hashed, is_active=True, bot__is_active=True
        )


class BotUsage(BaseModel):
    api_key = models.ForeignKey(BotAPIKey, on_delete=models.CASCADE)
    tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)