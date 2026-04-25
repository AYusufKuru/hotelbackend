from django.urls import include, path

from .night_audit_views import NightAuditRunView
from .views import build_router

urlpatterns = [
    path("night-audit/run/", NightAuditRunView.as_view(), name="night-audit-run"),
    path("", include(build_router().urls)),
]