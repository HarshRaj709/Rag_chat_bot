# knowledge_base/urls.py
from django.urls import path

from .views import (
    KBListCreateView, 
    KBDetailView,
    KBDocumentDetailView,
    KBDocumentRetryView,
    KBIngestView,
)

urlpatterns = [
    path("orgs/<uuid:pk>/kbs/", KBListCreateView.as_view(), name="kb-list-create"),
    path("orgs/<uuid:pk>/kbs/<uuid:kb_pk>/", KBDetailView.as_view(), name="kb-detail"),
    path("orgs/<uuid:pk>/kbs/<uuid:kb_pk>/ingest/", KBIngestView.as_view(), name="kb-ingest"),
    # Same path as before (backward compatible):
    #   GET    -> poll ingestion status {status, chunk_count, error_message}
    #   DELETE -> delete document (DB + file now, vectors in background)
    path(
        "orgs/<uuid:pk>/kbs/<uuid:kb_pk>/documents/<uuid:doc_pk>/",
        KBDocumentDetailView.as_view(),
        name="kb-document-detail",
    ),
    path(
        "orgs/<uuid:pk>/kbs/<uuid:kb_pk>/documents/<uuid:doc_pk>/retry/",
        KBDocumentRetryView.as_view(),
        name="kb-document-retry",
    ),
]