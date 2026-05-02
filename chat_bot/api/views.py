import json, uuid, logging
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from asgiref.sync import sync_to_async

from common.rag import rag_service
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView, GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.views import View

from organization.models import Organisation
from chat_bot.models import Bot, BotAPIKey
from common.permissions import IsOrgMember
from .serializers import BotSerializer, BotDetailSerializer

logger = logging.getLogger(__name__)

class BotListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = BotSerializer

    def get_org(self):
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_queryset(self):
        return Bot.objects.filter(
            org=self.get_org(), is_active=True
        ).prefetch_related("kbs", "api_keys")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bot = serializer.save()

        data = serializer.data
        data["api_key"] = getattr(bot, "_raw_api_key", None) #raw_key
        return Response(data, status=status.HTTP_201_CREATED)


class BotDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = BotDetailSerializer
    http_method_names = ["get", "patch"]

    def get_org(self):
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_object(self):
        return get_object_or_404(
            Bot,
            pk=self.kwargs["bot_pk"],
            org=self.get_org(),
            is_active=True,
        )


class BotDeactivateView(GenericAPIView):
    """
    soft delete bots
    """
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_org(self):
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org

    def post(self, request, *args, **kwargs):
        bot = get_object_or_404(
            Bot,
            pk=self.kwargs["bot_pk"],
            org=self.get_org(),
            is_active=True,
        )
        bot.is_active = False
        bot.save(update_fields=["is_active"])
        return Response({"detail": "Bot deactivated."}, status=status.HTTP_200_OK)
    
class BotAPIKeyRotateView(GenericAPIView):
    """
    Revokes all existing keys and generates a fresh one.
    """
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_org(self):
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org

    def post(self, request, *args, **kwargs):
        bot = get_object_or_404(
            Bot,
            pk=self.kwargs["bot_pk"],
            org=self.get_org(),
            is_active=True,
        )

        # deactivate keys
        bot.api_keys.filter(is_active=True).update(is_active=False)
        _, raw_key = BotAPIKey.generate(bot, name="default")

        return Response({
            "detail": "Previous keys revoked. Copy your new key — it will not be shown again.",
            "api_key": raw_key,
            "prefix": raw_key[:12],
        }, status=status.HTTP_201_CREATED)

@method_decorator(csrf_exempt, name="dispatch")
class BotChatView(View):
    """
    POST /api/bot/{slug}/chat/
    Authorization: Bearer ragbot_live_xxxx
    { "query": "...", "session_id": "required" }
    Public endpoint — no org context, auth via API key.
    """

    async def post(self, request, slug: str):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JsonResponse({"error": "Missing or invalid Authorization header."}, status=401)

        raw_key = auth[len("Bearer "):]
        try:
            api_key_obj = await sync_to_async(BotAPIKey.verify)(raw_key)
        except BotAPIKey.DoesNotExist:
            return JsonResponse({"error": "Invalid or inactive API key."}, status=401)

        bot = api_key_obj.bot

        if bot.slug != slug:
            return JsonResponse({"error": "API key does not match this bot."}, status=403)

        try:
            body = json.loads(request.body)
            query = body.get("query", "").strip()
            session_id = body.get("session_id", "").strip()
            if not session_id:
                return JsonResponse({"error": "session_id is required."}, status=400)
            # session_id = body.get("session_id") or str(uuid.uuid4())
        except Exception:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        if not query:
            return JsonResponse({"error": "query is required."}, status=400)

        async def event_stream():
            try:
                async for token in rag_service.stream(bot, session_id, query):
                    yield f"data: {json.dumps({'token': token, 'session_id': session_id})}\n\n"
                yield f"data: {json.dumps({'token': '', 'session_id': session_id, 'done': True})}\n\n"
            except Exception as e:
                logger.exception("Streaming error")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )
    
# uvicorn custom_chat_bot.asgi:application --reload