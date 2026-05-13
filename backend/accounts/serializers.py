from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class LoginSerializer(TokenObtainPairSerializer):
    """Kullanıcı adı + şifre ile JWT; yanıtta temel kullanıcı bilgisi."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data["user"] = {
            "id": user.pk,
            "username": user.username,
            "email": user.email or "",
            "is_superuser": user.is_superuser,
        }
        return data
