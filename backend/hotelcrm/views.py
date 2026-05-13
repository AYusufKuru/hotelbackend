from django.apps import apps
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .serializers import get_serializer


def _viewset_for(model):
    ser = get_serializer(model)

    class VS(ModelViewSet):
        queryset = model.objects.all()
        serializer_class = ser
        permission_classes = [IsAuthenticated]

    VS.__name__ = f"{model.__name__}ViewSet"
    VS.__qualname__ = VS.__name__
    return VS


def build_router():
    from rest_framework.routers import DefaultRouter

    from .rbac_views import HotelModuleOverrideScopedViewSet, UserRoleScopedViewSet

    router = DefaultRouter()
    skip_model = frozenset({"userrole", "hotelmoduleoverride"})
    for model in apps.get_app_config("hotelcrm").get_models():
        if model._meta.model_name in skip_model:
            continue
        prefix = model._meta.model_name.replace("_", "-")
        router.register(prefix, _viewset_for(model), basename=prefix)
    router.register("userrole", UserRoleScopedViewSet, basename="userrole")
    router.register(
        "hotelmoduleoverride",
        HotelModuleOverrideScopedViewSet,
        basename="hotelmoduleoverride",
    )
    return router
