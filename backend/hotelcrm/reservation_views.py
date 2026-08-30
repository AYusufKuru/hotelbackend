from django.db import transaction
from rest_framework.viewsets import ModelViewSet

from hotelcrm.activity_log import extract_hotel_id
from hotelcrm.api_access import assert_payload_hotel_matches_request, scope_queryset_to_hotel
from hotelcrm.models.reservation_folio import Reservation
from hotelcrm.permissions import HasHotelModule
from hotelcrm.reservation_availability import check_room_availability, merged_stay_fields
from hotelcrm.serializers import ReservationSerializer


class ReservationViewSet(ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    permission_classes = [HasHotelModule]
    required_modules = (
        "front-office",
        "res-list",
        "res-card",
        "new-reservation",
        "reservations-tape",
        "checkout",
        "room-rack",
        "folio",
        "group-res",
        "kbs",
        "guest-inform",
        "night-audit",
    )

    def get_queryset(self):
        hotel_id = extract_hotel_id(self.request)
        if not hotel_id:
            return Reservation.objects.none()
        return scope_queryset_to_hotel(Reservation, hotel_id)

    @transaction.atomic
    def perform_create(self, serializer):
        assert_payload_hotel_matches_request(self.request, serializer)
        room, check_in, check_out, status = merged_stay_fields(None, serializer.validated_data)
        check_room_availability(
            room=room,
            check_in=check_in,
            check_out=check_out,
            status=status,
            lock_room=True,
        )
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        assert_payload_hotel_matches_request(self.request, serializer)
        instance = serializer.instance
        room, check_in, check_out, status = merged_stay_fields(instance, serializer.validated_data)
        check_room_availability(
            room=room,
            check_in=check_in,
            check_out=check_out,
            status=status,
            exclude_reservation_id=instance.pk,
            lock_room=True,
        )
        serializer.save()
