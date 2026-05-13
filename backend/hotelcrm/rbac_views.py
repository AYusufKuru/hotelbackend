from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from hotelcrm.models import HotelModuleOverride, UserRole
from hotelcrm.rbac import can_manage_modules, can_manage_users
from hotelcrm.serializers import get_serializer


class UserRoleScopedViewSet(ModelViewSet):
    """Otel bazlı kullanıcı–rol ataması; liste için `?hotel=` zorunlu."""

    serializer_class = get_serializer(UserRole)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = UserRole.objects.select_related("user", "role", "hotel").order_by("user__username")
        hotel = self.request.query_params.get("hotel")
        if not hotel:
            return UserRole.objects.none()
        if not (self.request.user.is_superuser or can_manage_users(self.request.user, hotel)):
            return UserRole.objects.none()
        return qs.filter(hotel_id=hotel)

    def perform_create(self, serializer):
        hotel_id = str(serializer.validated_data.get("hotel"))
        if not hotel_id or not (
            self.request.user.is_superuser or can_manage_users(self.request.user, hotel_id)
        ):
            raise PermissionDenied("Kullanıcı rolü atama yetkisi yok.")
        serializer.save()

    def perform_update(self, serializer):
        hotel_id = str(serializer.instance.hotel_id)
        if not (self.request.user.is_superuser or can_manage_users(self.request.user, hotel_id)):
            raise PermissionDenied("Kullanıcı rolü güncelleme yetkisi yok.")
        serializer.save()

    def perform_destroy(self, instance):
        hotel_id = str(instance.hotel_id)
        if not (self.request.user.is_superuser or can_manage_users(self.request.user, hotel_id)):
            raise PermissionDenied("Kullanıcı rolü silme yetkisi yok.")
        instance.delete()


class HotelModuleOverrideScopedViewSet(ModelViewSet):
    """Otel modül görünürlü listesi; `?hotel=` ile filtre. Yazma: modules.manage."""

    serializer_class = get_serializer(HotelModuleOverride)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        hotel = self.request.query_params.get("hotel")
        if not hotel:
            return HotelModuleOverride.objects.none()
        qs = (
            HotelModuleOverride.objects.select_related("hotel")
            .filter(hotel_id=hotel)
            .order_by("module_id")
        )
        if self.request.user.is_superuser or can_manage_modules(self.request.user, hotel):
            return qs
        return HotelModuleOverride.objects.none()

    def perform_create(self, serializer):
        hotel_id = str(serializer.validated_data.get("hotel"))
        if not hotel_id or not can_manage_modules(self.request.user, hotel_id):
            raise PermissionDenied("Modül yapılandırma yetkisi yok.")
        serializer.save()

    def perform_update(self, serializer):
        hotel_id = str(serializer.instance.hotel_id)
        if not can_manage_modules(self.request.user, hotel_id):
            raise PermissionDenied("Modül yapılandırma yetkisi yok.")
        serializer.save()

    def perform_destroy(self, instance):
        hotel_id = str(instance.hotel_id)
        if not can_manage_modules(self.request.user, hotel_id):
            raise PermissionDenied("Modül yapılandırma yetkisi yok.")
        instance.delete()
