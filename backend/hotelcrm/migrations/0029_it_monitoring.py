# Generated manually for IT monitoring

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0028_minibar_stock_integration"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationconnection",
            name="monitor_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="agent_token",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="host_hostname",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="uptime_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="last_heartbeat_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="cpu_percent",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="memory_percent",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="disk_percent",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="network_mbps_in",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="integrationconnection",
            name="network_mbps_out",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.CreateModel(
            name="ItMetricSample",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("cpu_percent", models.DecimalField(decimal_places=2, max_digits=5)),
                ("memory_percent", models.DecimalField(decimal_places=2, max_digits=5)),
                ("disk_percent", models.DecimalField(decimal_places=2, max_digits=5)),
                ("network_mbps_in", models.DecimalField(decimal_places=3, default=0, max_digits=10)),
                ("network_mbps_out", models.DecimalField(decimal_places=3, default=0, max_digits=10)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "integration",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metric_samples",
                        to="hotelcrm.integrationconnection",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_itmetricsample",
                "ordering": ["-recorded_at"],
            },
        ),
        migrations.CreateModel(
            name="ItAlarmWebhook",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("target_url", models.URLField(max_length=512)),
                ("secret_header", models.CharField(blank=True, max_length=128)),
                ("is_enabled", models.BooleanField(default=True)),
                ("cpu_threshold", models.PositiveSmallIntegerField(default=80)),
                ("memory_threshold", models.PositiveSmallIntegerField(default=85)),
                ("disk_threshold", models.PositiveSmallIntegerField(default=90)),
                ("offline_minutes", models.PositiveSmallIntegerField(default=5)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="it_alarm_webhooks",
                        to="hotelcrm.hotel",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_italarmwebhook",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ItAlertLog",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("alert_kind", models.CharField(max_length=32)),
                ("severity", models.CharField(default="warning", max_length=16)),
                ("message", models.TextField()),
                ("webhook_status", models.CharField(blank=True, max_length=16)),
                ("webhook_response", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="it_alert_logs",
                        to="hotelcrm.hotel",
                    ),
                ),
                (
                    "integration",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="alert_logs",
                        to="hotelcrm.integrationconnection",
                    ),
                ),
                (
                    "webhook",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="delivery_logs",
                        to="hotelcrm.italarmwebhook",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_italertlog",
                "ordering": ["-created_at"],
            },
        ),
    ]
