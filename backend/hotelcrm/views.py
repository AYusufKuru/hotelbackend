from django.apps import apps
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from hotelcrm.activity_log import extract_hotel_id
from hotelcrm.api_access import (
    assert_payload_hotel_matches_request,
    modules_for_model,
    scope_queryset_to_hotel,
)
from hotelcrm.models import Hotel
from hotelcrm.permissions import HasHotelModule
from hotelcrm.rbac import hotel_ids_for_user, permission_codes_for_user, user_belongs_to_hotel
from hotelcrm.serializers import get_serializer

from .hr_recruitment_views import HotelRecruitmentScopedViewSet
from .reservation_views import ReservationViewSet


def _viewset_for(model):
    ser = get_serializer(model)
    modules = modules_for_model(model)

    class VS(ModelViewSet):
        queryset = model.objects.all()
        serializer_class = ser
        permission_classes = [HasHotelModule]
        required_modules = modules

        def get_queryset(self):
            hotel_id = extract_hotel_id(self.request)
            if not hotel_id:
                return model.objects.none()
            return scope_queryset_to_hotel(
                model,
                hotel_id,
                superuser=bool(self.request.user.is_superuser),
            )

        def perform_create(self, serializer):
            assert_payload_hotel_matches_request(self.request, serializer)
            serializer.save()

        def perform_update(self, serializer):
            assert_payload_hotel_matches_request(self.request, serializer)
            serializer.save()

    VS.__name__ = f"{model.__name__}ViewSet"
    VS.__qualname__ = VS.__name__
    return VS


class HotelScopedViewSet(ModelViewSet):
    """Otel listesi: kullanıcının üye olduğu tesisler. Yazma kısıtlı."""

    serializer_class = get_serializer(Hotel)
    permission_classes = [IsAuthenticated]
    queryset = Hotel.objects.all()
    allow_without_hotel = True

    def get_queryset(self):
        ids = hotel_ids_for_user(self.request.user)
        if not ids:
            return Hotel.objects.none()
        return Hotel.objects.filter(pk__in=ids).order_by("name")

    def perform_create(self, serializer):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Yeni otel yalnızca süper kullanıcı oluşturabilir.")
        serializer.save()

    def perform_update(self, serializer):
        hotel = serializer.instance
        user = self.request.user
        if not user_belongs_to_hotel(user, str(hotel.pk)):
            raise PermissionDenied("Bu otele erişiminiz yok.")
        perms = permission_codes_for_user(user, str(hotel.pk))
        if not (
            user.is_superuser
            or perms.intersection(
                {
                    "modules.manage",
                    "mod.all",
                    "mod.global-vision",
                    "mod.purchasing",
                    "mod.room-inventory-admin",
                }
            )
        ):
            raise PermissionDenied("Otel kaydını güncelleme yetkisi yok.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Otel silme yetkisi yok.")
        instance.delete()


def build_router():
    from rest_framework.routers import DefaultRouter

    from .rbac_views import (
        HotelModuleOverrideScopedViewSet,
        PermissionCatalogViewSet,
        RoleCatalogViewSet,
        UserRoleScopedViewSet,
    )
    from .staff_views import StaffMemberScopedViewSet

    router = DefaultRouter()
    skip_model = frozenset(
        {
            "userrole",
            "hotelmoduleoverride",
            "hotelrecruitment",
            "staffmember",
            "reservation",
            "auditlog",
            "role",
            "permission",
            "rolepermission",
            "usermodulegrant",
            "hotel",
        }
    )
    for model in apps.get_app_config("hotelcrm").get_models():
        if model._meta.model_name in skip_model:
            continue
        prefix = model._meta.model_name.replace("_", "-")
        router.register(prefix, _viewset_for(model), basename=prefix)
    router.register("hotel", HotelScopedViewSet, basename="hotel")
    router.register("reservation", ReservationViewSet, basename="reservation")
    router.register("role", RoleCatalogViewSet, basename="role")
    router.register("permission", PermissionCatalogViewSet, basename="permission")
    router.register("userrole", UserRoleScopedViewSet, basename="userrole")
    router.register(
        "hotelmoduleoverride",
        HotelModuleOverrideScopedViewSet,
        basename="hotelmoduleoverride",
    )
    router.register(
        "hotel-recruitment",
        HotelRecruitmentScopedViewSet,
        basename="hotel-recruitment",
    )
    router.register("staffmember", StaffMemberScopedViewSet, basename="staffmember")
    return router
