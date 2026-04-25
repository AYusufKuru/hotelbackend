import uuid

from django.db import models

from .enums import StaffStatus
from .property_guest import Hotel


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=128)

    class Meta:
        db_table = "hotelcrm_department"


class StaffMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="staff_members")
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=255)
    job_title = models.CharField(max_length=128, blank=True)
    shift_window = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=StaffStatus.choices)
    phone = models.CharField(max_length=64, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    monthly_wage = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "hotelcrm_staffmember"
