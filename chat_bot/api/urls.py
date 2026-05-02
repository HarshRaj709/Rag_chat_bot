# bot/urls.py
from django.urls import path
from .views import BotListCreateView, BotDetailView, BotDeactivateView, BotChatView, BotAPIKeyRotateView

urlpatterns = [
    path("orgs/<uuid:pk>/bots/", BotListCreateView.as_view(), name="bot-list-create"),
    path("orgs/<uuid:pk>/bots/<uuid:bot_pk>/", BotDetailView.as_view(), name="bot-detail"),
    path("orgs/<uuid:pk>/bots/<uuid:bot_pk>/deactivate/", BotDeactivateView.as_view(), name="bot-deactivate"),
    # path("orgs/<uuid:pk>/bots/<uuid:bot_pk>/keys/", BotAPIKeyListView.as_view(), name="bot-keys"),
    path("orgs/<uuid:pk>/bots/<uuid:bot_pk>/keys/rotate/", BotAPIKeyRotateView.as_view(), name="bot-key-rotate"),

    path("bot/<slug:slug>/chat/", BotChatView.as_view(), name="bot-chat"),
]