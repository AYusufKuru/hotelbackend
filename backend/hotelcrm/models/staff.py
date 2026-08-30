import uuid

from django.conf import settings
from django.db import models

from .enums import StaffAbsenceReason, StaffOnboardingStatus, StaffStatus
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
    email = models.EmailField(blank=True)
    national_id = models.CharField(max_length=11, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    monthly_wage = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    hr_profile = models.JSONField(default=dict, blank=True)
    onboarding_status = models.CharField(
        max_length=16,
        choices=StaffOnboardingStatus.choices,
        default=StaffOnboardingStatus.ACTIVE,
        db_index=True,
    )
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_member_links",
    )

    class Meta:
        db_table = "hotelcrm_staffmember"


def _empty_recruitment_data():
    return {"jobs": [], "candidates": []}


class HotelRecruitment(models.Model):
    """Otel bazlı iş ilanı ve aday havuzu (işe alım kanban)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.OneToOneField(
        Hotel,
        on_delete=models.CASCADE,
        related_name="recruitment_board",
    )
    data = models.JSONField(default=_empty_recruitment_data, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hotelcrm_hotelrecruitment"

    def __str__(self):
        return f"Recruitment ({self.hotel_id})"


class StaffAbsenceReport(models.Model):
    """Personel devamsızlık / eksik gün bildirimi (tarih ve gerekçe ile)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="staff_absence_reports")
    staff_member = models.ForeignKey(
        StaffMember,
        on_delete=models.CASCADE,
        related_name="absence_reports",
    )
    absence_date = models.DateField()
    reason = models.CharField(max_length=32, choices=StaffAbsenceReason.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_staffabsencereport"
        ordering = ["-absence_date", "-created_at"]
