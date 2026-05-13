import re
import uuid

from django.db import models, transaction

from .enums import BoardBasis, FolioLineType, ReservationStatus
from .property_guest import Channel, Guest, Hotel, Room, RoomType


class ReservationOccupant(models.Model):
    """Konaklamadaki her misafir (birincil + ek kişiler) — rezervasyon `guest` ile birlikte kullanılır."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(
        "Reservation",
        on_delete=models.CASCADE,
        related_name="occupants",
    )
    guest = models.ForeignKey(
        Guest,
        on_delete=models.CASCADE,
        related_name="reservation_occupant_links",
    )
    is_primary = models.BooleanField(default=False)
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "hotelcrm_reservationoccupant"
        ordering = ["sequence", "id"]


class Reservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="reservations")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    guest = models.ForeignKey(Guest, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations")
    primary_guest_name = models.CharField(max_length=255)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations")
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_by_type",
    )
    channel = models.ForeignKey(Channel, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations")
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    nights = models.PositiveIntegerField()
    adults = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=32, choices=ReservationStatus.choices)
    board_basis = models.CharField(max_length=8, choices=BoardBasis.choices, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.display_code and self.hotel_id:
            with transaction.atomic():
                hotel = Hotel.objects.select_for_update().get(pk=self.hotel_id)
                hotel.reservation_sequence = (hotel.reservation_sequence or 0) + 1
                hotel.save(update_fields=["reservation_sequence"])
                seq = hotel.reservation_sequence
                base = re.sub(r"[^A-Z0-9]", "", (hotel.code or "").upper()) or "RES"
                self.display_code = f"{base}-R{seq}"
        if not self.channel_id and self.hotel_id:
            ch = Channel.objects.filter(hotel_id=self.hotel_id, name="Direkt").first()
            if not ch:
                ch = Channel.objects.create(
                    hotel_id=self.hotel_id,
                    name="Direkt",
                    code="DIRECT",
                )
            self.channel = ch
        super().save(*args, **kwargs)

    class Meta:
        db_table = "hotelcrm_reservation"


class Folio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name="folio")
    currency = models.CharField(max_length=3, default="TRY")
    opened_on = models.DateField()
    closed_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "hotelcrm_folio"


class FolioLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folio = models.ForeignKey(Folio, on_delete=models.CASCADE, related_name="lines")
    line_type = models.CharField(max_length=32, choices=FolioLineType.choices)
    description = models.CharField(max_length=512)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    posted_date = models.DateField()
    source_module = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_folioline"
