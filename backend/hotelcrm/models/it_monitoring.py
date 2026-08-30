import uuid

from django.db import models

from .property_guest import Hotel
from .extended import IntegrationConnection


class ItMetricSample(models.Model):
    id = models.BigAutoField(primary_key=True)
    integration = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        related_name="metric_samples",
    )
    cpu_percent = models.DecimalField(max_digits=5, decimal_places=2)
    memory_percent = models.DecimalField(max_digits=5, decimal_places=2)
    disk_percent = models.DecimalField(max_digits=5, decimal_places=2)
    network_mbps_in = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    network_mbps_out = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_itmetricsample"
        ordering = ["-recorded_at"]


class ItAlarmWebhook(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="it_alarm_webhooks")
    name = models.CharField(max_length=128)
    target_url = models.URLField(max_length=512)
    secret_header = models.CharField(max_length=128, blank=True)
    is_enabled = models.BooleanField(default=True)
    cpu_threshold = models.PositiveSmallIntegerField(default=80)
    memory_threshold = models.PositiveSmallIntegerField(default=85)
    disk_threshold = models.PositiveSmallIntegerField(default=90)
    offline_minutes = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_italarmwebhook"
        ordering = ["name"]


class ItAlertLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="it_alert_logs")
    integration = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alert_logs",
    )
    webhook = models.ForeignKey(
        ItAlarmWebhook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_logs",
    )
    alert_kind = models.CharField(max_length=32)
    severity = models.CharField(max_length=16, default="warning")
    message = models.TextField()
    webhook_status = models.CharField(max_length=16, blank=True)
    webhook_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_italertlog"
        ordering = ["-created_at"]
