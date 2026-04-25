import re
import uuid

from django.db import models, transaction

from .enums import (
    HousekeepingCleanStatus,
    LoyaltyTier,
    RoomOccupancyStatus,
)


class Hotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=128, blank=True)
    property_type = models.CharField(max_length=32, blank=True)
    capacity_rooms = models.PositiveIntegerField(null=True, blank=True)
    # Otel bazlı misafir görünür kodu için sayaç (örn. STB-421).
    guest_sequence = models.PositiveIntegerField(default=0)
    # Rezervasyon görünür kodu için sayaç (örn. STB-R12).
    reservation_sequence = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_hotel"


class RoomType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="room_types")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    default_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_occupancy = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "hotelcrm_roomtype"
        unique_together = [("hotel", "code")]


class Channel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True, related_name="channels")
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hotelcrm_channel"


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="rooms")
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms")
    room_number = models.CharField(max_length=16)
    floor = models.IntegerField(null=True, blank=True)
    occupancy_status = models.CharField(
        max_length=32,
        choices=RoomOccupancyStatus.choices,
        default=RoomOccupancyStatus.VACANT,
    )
    clean_status = models.CharField(
        max_length=16,
        choices=HousekeepingCleanStatus.choices,
        default=HousekeepingCleanStatus.CLEAN,
    )

    class Meta:
        db_table = "hotelcrm_room"
        unique_together = [("hotel", "room_number")]


class Guest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True, related_name="guests")
    # Görünür misafir kodu (örn. STB-421); UUID API/internal id olarak kalır.
    display_code = models.CharField(max_length=48, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=255)
    nationality = models.CharField(max_length=2, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    loyalty_tier = models.CharField(
        max_length=16,
        choices=LoyaltyTier.choices,
        default=LoyaltyTier.NONE,
    )
    visit_count = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    last_visit_date = models.DateField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    national_id = models.CharField(max_length=32, blank=True)
    passport_no = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_guest"

    def save(self, *args, **kwargs):
        if not self.display_code and self.hotel_id:
            with transaction.atomic():
                hotel = Hotel.objects.select_for_update().get(pk=self.hotel_id)
                hotel.guest_sequence += 1
                hotel.save(update_fields=["guest_sequence"])
                seq = hotel.guest_sequence
            # Otel kodu (benzersiz) + sıra → STB-421; UUID ile karışmaz, global benzersiz string.
            base = re.sub(r"[^A-Z0-9]", "", (hotel.code or "").upper()) or "GUEST"
            self.display_code = f"{base}-{seq}"
        super().save(*args, **kwargs)
