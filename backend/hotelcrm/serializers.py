"""ModelSerializer üretimi — tüm hotelcrm modelleri için fields='__all__'."""
from rest_framework import serializers


def _serializer(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    name = f"{model.__name__}Serializer"
    return type(name, (serializers.ModelSerializer,), {"Meta": meta})


_SERIALIZER_CACHE = {}


def get_serializer(model):
    if model not in _SERIALIZER_CACHE:
        _SERIALIZER_CACHE[model] = _serializer(model)
    return _SERIALIZER_CACHE[model]
