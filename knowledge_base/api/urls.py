# knowledge_base/urls.py
from django.urls import path
from .views import (
    KBListCreateView, 
    KBDetailView,
    KBIngestView,
    KBDocumentDeleteView,
)

urlpatterns = [
    path("orgs/<uuid:pk>/kbs/", KBListCreateView.as_view(), name="kb-list-create"),
    path("orgs/<uuid:pk>/kbs/<uuid:kb_pk>/", KBDetailView.as_view(), name="kb-detail"),
    path("orgs/<uuid:pk>/kbs/<uuid:kb_pk>/ingest/", KBIngestView.as_view(), name="kb-ingest"),
    path("orgs/<uuid:pk>/kbs/<uuid:kb_pk>/documents/<uuid:doc_pk>/", KBDocumentDeleteView.as_view(), name="kb-document-delete"),
]