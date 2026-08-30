from django.urls import include, path

from .assistant_views import AssistantChatView
from .competitor_views import CompetitorAutoSearchView
from .access_views import (
    AccessActivityView,
    AccessAuditLogView,
    AccessHotelUserDetailView,
    AccessHotelUsersView,
    AccessModulePresetsView,
)
from .survey_views import SurveyRecipientsView, SurveySendView, SurveyStandardTemplateView
from .it_monitor_views import (
    ItMonitorCollectLocalView,
    ItMonitorHeartbeatView,
    ItMonitorSummaryView,
    ItMonitorWebhookTestView,
)
from .night_audit_views import NightAuditHistoryView, NightAuditRunView
from .views import build_router

urlpatterns = [
    path("it-monitor/heartbeat/", ItMonitorHeartbeatView.as_view(), name="it-monitor-heartbeat"),
    path("it-monitor/collect-local/", ItMonitorCollectLocalView.as_view(), name="it-monitor-collect-local"),
    path("it-monitor/webhook-test/", ItMonitorWebhookTestView.as_view(), name="it-monitor-webhook-test"),
    path("it-monitor/summary/", ItMonitorSummaryView.as_view(), name="it-monitor-summary"),
    path("survey/template/", SurveyStandardTemplateView.as_view(), name="survey-template"),
    path("survey/recipients/", SurveyRecipientsView.as_view(), name="survey-recipients"),
    path("survey/send/", SurveySendView.as_view(), name="survey-send"),
    path("access/hotel-users/", AccessHotelUsersView.as_view(), name="access-hotel-users"),
    path(
        "access/hotel-users/<int:user_id>/",
        AccessHotelUserDetailView.as_view(),
        name="access-hotel-user-detail",
    ),
    path("access/module-presets/", AccessModulePresetsView.as_view(), name="access-module-presets"),
    path("access/activity/", AccessActivityView.as_view(), name="access-activity"),
    path("access/audit-logs/", AccessAuditLogView.as_view(), name="access-audit-logs"),
    path("night-audit/run/", NightAuditRunView.as_view(), name="night-audit-run"),
    path("night-audit/history/", NightAuditHistoryView.as_view(), name="night-audit-history"),
    path(
        "competitors/auto-search/",
        CompetitorAutoSearchView.as_view(),
        name="competitors-auto-search",
    ),
    path("assistant/chat/", AssistantChatView.as_view(), name="assistant-chat"),
    path("", include(build_router().urls)),
]