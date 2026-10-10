import json, uuid, logging
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from django.db.models import Count, Prefetch, Sum, Value
from django.db.models.functions import Coalesce
from asgiref.sync import sync_to_async
from urllib.parse import urlparse
from common.rag import get_rag_service
from common.mixins import GetOrgMixin
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView, GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.views import View

from organization.models import Organisation
from knowledge_base.models import KnowledgeBase
from chat_bot.models import Bot, BotAPIKey
from common.permissions import IsOrgMember
from .serializers import BotSerializer, BotDetailSerializer

logger = logging.getLogger(__name__)

class BotListCreateView(GetOrgMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = BotSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_queryset(self):
        return Bot.objects.filter(
            org=self.get_org(), is_active=True
        ).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bot = serializer.save()

        data = serializer.data
        data["api_key"] = getattr(bot, "_raw_api_key", None) #raw_key
        return Response(data, status=status.HTTP_201_CREATED)


class BotDetailView(GetOrgMixin, RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = BotDetailSerializer
    http_method_names = ["get", "patch"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_object(self):
        annotated_kbs = KnowledgeBase.objects.annotate(
            annotated_document_count=Count("documents", distinct=True),
            annotated_chunks_count=Coalesce(Sum("documents__chunk_count"), Value(0)),
        ).prefetch_related("documents")
        return get_object_or_404(
            Bot.objects.select_related("org").prefetch_related(
                Prefetch("kbs", queryset=annotated_kbs),
                "api_keys",
            ),
            pk=self.kwargs["bot_pk"],
            org=self.get_org(),
            is_active=True,
        )


class BotDeactivateView(GetOrgMixin, GenericAPIView):
    """
    soft delete bots
    """
    permission_classes = [IsAuthenticated, IsOrgMember]

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
    
class BotAPIKeyRotateView(GetOrgMixin, GenericAPIView):
    """
    Revokes all existing keys and generates a fresh one.
    """
    permission_classes = [IsAuthenticated, IsOrgMember]

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
            api_key_obj = await sync_to_async(BotAPIKey.verify)(raw_key)  #verification at each request, so we can revoke keys and rotate them, expensive as calling DB each time, but we can cache them in memory if needed
        except BotAPIKey.DoesNotExist:
            return JsonResponse({"error": "Invalid or inactive API key."}, status=401)

        bot = api_key_obj.bot

        if bot.slug != slug:
            return JsonResponse({"error": "API key does not match this bot."}, status=403)
        
        origin = request.headers.get("Origin")
        allowed_domains = bot.allowed_domains or []

        # Enforce only when allowlist is configured and Origin is present.
        # Empty allowlist = allow all (dev / direct API use).
        # Missing Origin = non-browser client (Postman/curl) — skip check.
        if origin and allowed_domains:
            parsed = urlparse(origin)
            hostname = parsed.hostname

            if hostname not in allowed_domains:
                return JsonResponse(
                    {
                        "error": f"Domain '{hostname}' is not allowed."
                    },
                    status=403,
                )

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
                service = get_rag_service()  # lazy singleton, lives on the ASGI loop only
                async for token in service.stream(bot, session_id, query):
                    yield f"data: {json.dumps({'token': token, 'session_id': session_id})}\n\n"
                yield f"data: {json.dumps({'token': '', 'session_id': session_id, 'done': True})}\n\n"
            except Exception as e:
                logger.exception("Streaming error")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"

        sse_headers = {
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        if origin:
            sse_headers["Access-Control-Allow-Origin"] = origin

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
            headers=sse_headers,
        )
    
# uvicorn custom_chat_bot.asgi:application --reload

# ragbot_live_jLtFJqXs67WzwxzG_j-_C71f9TxTHQaG9kQjVi6nTio