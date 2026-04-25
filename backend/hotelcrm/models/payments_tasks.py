import uuid

from django.db import models

from .enums import CashFlowType, PaymentMethod, TaskCategory, TaskStatus
from .property_guest import Hotel, Room
from .reservation_folio import Reservation
from .staff import StaffMember


class CashTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="cash_transactions")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    flow_type = models.CharField(max_length=16, choices=CashFlowType.choices)
    description = models.CharField(max_length=512)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=32, choices=PaymentMethod.choices, blank=True)
    tx_date = models.DateField()
    tx_time = models.TimeField(null=True, blank=True)
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_cashtransaction"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=32, choices=PaymentMethod.choices)
    paid_at = models.DateTimeField(auto_now_add=True)
    cash_transaction = models.ForeignKey(
        CashTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    class Meta:
        db_table = "hotelcrm_payment"


class OperationalTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="operational_tasks")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    category = models.CharField(max_length=32, choices=TaskCategory.choices)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    title = models.CharField(max_length=512)
    priority = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=32, choices=TaskStatus.choices)
    assignee = models.ForeignKey(
        StaffMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_operationaltask"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    notif_type = models.CharField(max_length=16, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_notification"
        ordering = ["-created_at"]
