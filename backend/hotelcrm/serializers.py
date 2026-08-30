"""ModelSerializer üretimi — çoğu hotelcrm modeli fields='__all__'; Guest ayrı doğrulanır."""

from rest_framework import serializers

from hotelcrm.models.authz import UserRole
from hotelcrm.models.property_guest import Guest
from hotelcrm.models.reservation_folio import Reservation
from hotelcrm.reservation_availability import (
    check_room_availability,
    merged_stay_fields,
    require_room_for_blocking_reservation,
)


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


class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = "__all__"

    def validate(self, attrs):
        room, check_in, check_out, status = merged_stay_fields(self.instance, attrs)
        require_room_for_blocking_reservation(
            instance=self.instance,
            room=room,
            status=status,
        )
        check_room_availability(
            room=room,
            check_in=check_in,
            check_out=check_out,
            status=status,
            exclude_reservation_id=getattr(self.instance, "pk", None),
            lock_room=False,
        )
        return attrs


class UserRoleSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = UserRole
        fields = (
            "id",
            "user",
            "user_username",
            "role",
            "role_code",
            "role_name",
            "hotel",
        )


def _serializer(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    name = f"{model.__name__}Serializer"
    return type(name, (serializers.ModelSerializer,), {"Meta": meta})


_SERIALIZER_CACHE = {}


def get_serializer(model):
    if model not in _SERIALIZER_CACHE:
        if model is Guest:
            _SERIALIZER_CACHE[model] = GuestSerializer
        elif model is Reservation:
            _SERIALIZER_CACHE[model] = ReservationSerializer
        elif model is UserRole:
            _SERIALIZER_CACHE[model] = UserRoleSerializer
        else:
            _SERIALIZER_CACHE[model] = _serializer(model)
    return _SERIALIZER_CACHE[model]
