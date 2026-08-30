from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from hotelcrm.activity_log import extract_hotel_id
from hotelcrm.models import HotelModuleOverride, Permission, Role, UserRole
from hotelcrm.permissions import HasHotelModule
from hotelcrm.rbac import can_manage_modules, can_manage_users
from hotelcrm.serializers import get_serializer


def _can_list_rbac_catalog(request) -> bool:
    if request.user.is_superuser:
        return True
    hotel = request.query_params.get("hotel")
    return bool(hotel) and can_manage_users(request.user, hotel)


class RoleCatalogViewSet(ReadOnlyModelViewSet):
    """Rol tanımları salt okunur; yazma yalnızca süper kullanıcı / seed."""

    queryset = Role.objects.all().order_by("name")
    serializer_class = get_serializer(Role)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not _can_list_rbac_catalog(self.request):
            return Role.objects.none()
        return Role.objects.all().order_by("name")


class PermissionCatalogViewSet(ReadOnlyModelViewSet):
    queryset = Permission.objects.all().order_by("code")
    serializer_class = get_serializer(Permission)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not _can_list_rbac_catalog(self.request):
            return Permission.objects.none()
        return Permission.objects.all().order_by("code")


class UserRoleScopedViewSet(ModelViewSet):
    """Otel bazlı kullanıcı–rol ataması; liste için `?hotel=` zorunlu."""

    serializer_class = get_serializer(UserRole)
    permission_classes = [HasHotelModule]
    required_modules = ("system-admin",)
    queryset = UserRole.objects.all()

    def get_queryset(self):
        qs = UserRole.objects.select_related("user", "role", "hotel").order_by("user__username")
        hotel = extract_hotel_id(self.request)
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
    permission_classes = [HasHotelModule]
    required_modules = ("system-admin",)
    queryset = HotelModuleOverride.objects.all()

    def get_queryset(self):
        hotel = extract_hotel_id(self.request)
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
