from django.urls import include, path

from .assistant_views import AssistantChatView
from .competitor_views import CompetitorAutoSearchView
from .night_audit_views import NightAuditRunView
from .views import build_router

urlpatterns = [
    path("night-audit/run/", NightAuditRunView.as_view(), name="night-audit-run"),
    path(
        "competitors/auto-search/",
        CompetitorAutoSearchView.as_view(),
        name="competitors-auto-search",
    ),
    path("assistant/chat/", AssistantChatView.as_view(), name="assistant-chat"),
    path("", include(build_router().urls)),
]