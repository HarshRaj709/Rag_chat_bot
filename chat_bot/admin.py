from django.contrib import admin
from chat_bot.models import Bot, BotAPIKey, BotUsage

# Register your models here.
admin.site.register(Bot)
admin.site.register(BotAPIKey)
admin.site.register(BotUsage)