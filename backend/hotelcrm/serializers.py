"""ModelSerializer üretimi — çoğu hotelcrm modeli fields='__all__'; Guest ayrı doğrulanır."""

from rest_framework import serializers

from hotelcrm.models.property_guest import Guest


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = "__all__"

    def validate(self, attrs):
        inst = self.instance
        raw_fn = attrs["first_name"] if "first_name" in attrs else getattr(inst, "first_name", "")
        raw_ln = attrs["last_name"] if "last_name" in attrs else getattr(inst, "last_name", "")
        fn = (raw_fn if raw_fn is not None else "").strip()
        ln = (raw_ln if raw_ln is not None else "").strip()
        if not fn and not ln:
            raise serializers.ValidationError(
                {"non_field_errors": ["Ad veya soyad zorunludur."]},
            )
        attrs["first_name"] = fn
        attrs["last_name"] = ln
        return attrs


def _serializer(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    name = f"{model.__name__}Serializer"
    return type(name, (serializers.ModelSerializer,), {"Meta": meta})


_SERIALIZER_CACHE = {}


def get_serializer(model):
    if model not in _SERIALIZER_CACHE:
        if model is Guest:
            _SERIALIZER_CACHE[model] = GuestSerializer
        else:
            _SERIALIZER_CACHE[model] = _serializer(model)
    return _SERIALIZER_CACHE[model]
