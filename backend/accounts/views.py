from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import LoginSerializer


class SessionPingView(APIView):
    """GET /api/auth/session/ping/ — JWT + merkez lisans middleware (masaüstü periyodik ping)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"ok": True})


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — body: { \"username\", \"password\" }"""

    permission_classes = [AllowAny]
    serializer_class = LoginSerializer


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
