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

    router = DefaultRouter()
    for model in apps.get_app_config("hotelcrm").get_models():
        prefix = model._meta.model_name.replace("_", "-")
        router.register(prefix, _viewset_for(model), basename=prefix)
    return router
