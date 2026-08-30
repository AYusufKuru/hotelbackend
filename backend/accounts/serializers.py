from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from hotelcrm.activity_log import log_activity


class LoginSerializer(TokenObtainPairSerializer):
    """Kullanıcı adı + şifre ile JWT; yanıtta temel kullanıcı bilgisi."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        request = self.context.get("request")
        log_activity(
            action="login",
            message=f"{user.username} sisteme giriş yaptı",
            module="auth",
            actor=user,
            actor_label=user.username,
            request=request,
        )
        data["user"] = {
            "id": user.pk,
            "username": user.username,
            "email": user.email or "",
            "is_superuser": user.is_superuser,
        }
        return data
