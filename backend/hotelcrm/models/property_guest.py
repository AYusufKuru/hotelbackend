import re
import uuid

from django.db import models, transaction

from .enums import (
    HousekeepingCleanStatus,
    LoyaltyTier,
    RoomOccupancyStatus,
    RoomTypeBedLayout,
)


class Hotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=128, blank=True)
    property_type = models.CharField(max_length=32, blank=True)
    capacity_rooms = models.PositiveIntegerField(null=True, blank=True)
    # Harita / rakip karşılaştırma için konum bilgisi (boş = haritada gösterilmez).
    address = models.CharField(max_length=512, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # Otel bazlı misafir görünür kodu için sayaç (örn. STB-421).
    guest_sequence = models.PositiveIntegerField(default=0)
    # Rezervasyon görünür kodu için sayaç (örn. STB-R12).
    reservation_sequence = models.PositiveIntegerField(default=0)
    # Alım faturası / e-belge: alıcı (otel) vergi ve unvan bilgisi.
    tax_id = models.CharField(
        max_length=11,
        blank=True,
        default="",
        help_text="Otel VKN (10) veya yetkili TCKN (11)",
    )
    trade_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Ticari unvan (fatura üst bilgisi)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_hotel"


class CompetitorHotel(models.Model):
    """Otelin etrafındaki rakip oteller — haritada gösterilir, fiyat karşılaştırması için kullanılır.

    Fiyatlar şu an manuel girilir (yetkili otel personeli tarafından).
    İlerde harici API entegrasyonu (Booking/Expedia) için aynı tablo doldurulabilir.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(
        Hotel, on_delete=models.CASCADE, related_name="competitors"
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=512, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    star_rating = models.DecimalField(
        max_digits=2, decimal_places=1, null=True, blank=True
    )
    # Tek bir snapshot fiyat: en düşük standart oda gece ücreti (TL).
    current_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="TRY")
    # Kaynak — manuel girilmişse "manual"; API'den geliyorsa "booking", "expedia" vb.
    source = models.CharField(max_length=32, default="manual")
    last_observed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hotelcrm_competitorhotel"
        ordering = ["name"]


class RoomType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="room_types")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    default_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_occupancy = models.PositiveIntegerField(null=True, blank=True)
    # Eski kısaltma; yeni kayıtlarda öncelik bed_*_count ve bed_description alanlarında.
    bed_layout = models.CharField(
        max_length=32,
        choices=RoomTypeBedLayout.choices,
        default=RoomTypeBedLayout.UNSPECIFIED,
        blank=True,
    )
    bed_single_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Twin / tek kişilik yatak adedi.",
    )
    bed_double_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Çift kişilik (Queen / Full) yatak adedi.",
    )
    bed_king_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="King ebatta çift kişilik yatak adedi.",
    )
    bed_description = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Ranza, yatalı şezlong, özel yapı vb. serbest tanım.",
    )

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
    first_name = models.CharField(max_length=127, blank=True, default="")
    last_name = models.CharField(max_length=127, blank=True, default="")
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
