import uuid

from django.db import models

from .enums import RestaurantOrderStatus, SpaAppointmentStatus
from .property_guest import Hotel, Room
from .reservation_folio import Reservation


class MenuCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="menu_categories")
    name = models.CharField(max_length=128)

    class Meta:
        db_table = "hotelcrm_menucategory"


class MenuItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="menu_items")
    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    display_code = models.CharField(max_length=32, blank=True)
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_menuitem"


class RestaurantOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="restaurant_orders")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    table_label = models.CharField(max_length=64, blank=True)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="restaurant_orders")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restaurant_orders",
    )
    status = models.CharField(max_length=32, choices=RestaurantOrderStatus.choices)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    order_date = models.DateField()
    order_time = models.TimeField(null=True, blank=True)

    class Meta:
        db_table = "hotelcrm_restaurantorder"


class RestaurantOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(RestaurantOrder, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_lines")
    item_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_restaurantorderline"


class SpaService(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="spa_services")
    name = models.CharField(max_length=255)
    default_price = models.DecimalField(max_digits=12, decimal_places=2)
    default_therapist = models.CharField(max_length=128, blank=True)

    class Meta:
        db_table = "hotelcrm_spaservice"


class SpaAppointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="spa_appointments")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    guest_name = models.CharField(max_length=255)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="spa_appointments")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spa_appointments",
    )
    spa_service = models.ForeignKey(SpaService, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")
    service_name_snapshot = models.CharField(max_length=255)
    therapist_name = models.CharField(max_length=128, blank=True)
    appointment_date = models.DateField()
    appointment_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=SpaAppointmentStatus.choices)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_spaappointment"
