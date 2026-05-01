from rest_framework.response import Response
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView, UpdateAPIView, DestroyAPIView, GenericAPIView
from rest_framework.permissions import IsAuthenticated
from common.permissions import IsOrgAdmin, IsOrgMember
from knowledge_base.models import KnowledgeBase, KBDocument
from organization.models import Organisation
from .serializers import KnowledgeBaseSerializer
from django.shortcuts import get_object_or_404


class KBListCreateView(ListCreateAPIView):
    """
    GET  /orgs/{pk}/kbs/    → list all KBs in this org
    POST /orgs/{pk}/kbs/    → create a new KB
    Any org member can do both.
    """
    permission_classes = [IsAuthenticated, IsOrgMember, IsOrgAdmin]
    serializer_class = KnowledgeBaseSerializer

    def get_org(self):      #cache
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org

    def get_serializer_context(self):           #used to add org in serializer
        context = super().get_serializer_context()
        context["org"] = self.get_org()
        return context

    def get_queryset(self):
        return KnowledgeBase.objects.filter(org=self.get_org())
