from django.urls import path

from .hotel_session import HotelSessionView, UserLookupView
from .views import LoginView, RefreshView, SessionPingView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("session/ping/", SessionPingView.as_view(), name="auth-session-ping"),
    path("session/", HotelSessionView.as_view(), name="auth-session"),
    path("users/lookup/", UserLookupView.as_view(), name="auth-users-lookup"),
]
