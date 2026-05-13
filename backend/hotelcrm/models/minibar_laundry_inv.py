import uuid

from django.db import models

from .enums import LaundryOrderStatus
from .property_guest import Hotel, Room
from .reservation_folio import Reservation


class MinibarProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="minibar_products")
    display_code = models.CharField(max_length=32, blank=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_minibarproduct"


class MinibarCharge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="minibar_charges")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="minibar_charges")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="minibar_charges",
    )
    charge_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    billed_to_folio = models.BooleanField(default=False)

    class Meta:
        db_table = "hotelcrm_minibarcharge"


class MinibarChargeLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    charge = models.ForeignKey(MinibarCharge, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(MinibarProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name="lines")
    name_snapshot = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_minibarchargeline"


class LaundryPricelistItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="laundry_pricelist_items")
    name = models.CharField(max_length=128)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_laundrypricelistitem"


class LaundryOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="laundry_orders")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="laundry_orders")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="laundry_orders",
    )
    guest_name = models.CharField(max_length=255)
    order_date = models.DateField()
    ordered_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=LaundryOrderStatus.choices)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_laundryorder"


class LaundryOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    laundry_order = models.ForeignKey(LaundryOrder, on_delete=models.CASCADE, related_name="lines")
    pricelist_item = models.ForeignKey(
        LaundryPricelistItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_lines",
    )
    name_snapshot = models.CharField(max_length=128)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_laundryorderline"


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="inventory_items")
    display_code = models.CharField(max_length=32, blank=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    warehouse = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Depo / lokasyon (örn. Ana depo, Mutfak, HK)",
    )
    unit = models.CharField(max_length=32, blank=True)
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=2)
    min_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "hotelcrm_inventoryitem"
