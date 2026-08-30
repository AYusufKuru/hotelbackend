import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0029_it_monitoring"),
    ]

    operations = [
        migrations.CreateModel(
            name="HotelSurveySmsSettings",
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
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("mock", "Test (konsola yaz)"),
                            ("netgsm", "Netgsm"),
                            ("http", "HTTP Webhook"),
                        ],
                        default="mock",
                        max_length=16,
                    ),
                ),
                ("api_username", models.CharField(blank=True, max_length=128)),
                ("api_password", models.CharField(blank=True, max_length=256)),
                ("sender_id", models.CharField(blank=True, max_length=32)),
                ("webhook_url", models.URLField(blank=True, max_length=512)),
                (
                    "message_template",
                    models.TextField(
                        default=(
                            "Sayın {guest_name}, {hotel_name} konaklamanız için 2 dakikalık "
                            "anketimiz: {link} Teşekkürler."
                        ),
                    ),
                ),
                ("public_base_url", models.URLField(blank=True, max_length=512)),
                ("is_enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "hotel",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="survey_sms_settings",
                        to="hotelcrm.hotel",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_hotelsurveysmssettings",
            },
        ),
        migrations.CreateModel(
            name="SurveyInvitation",
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
                ("guest_name", models.CharField(max_length=255)),
                ("phone", models.CharField(max_length=32)),
                ("room_number", models.CharField(blank=True, max_length=16)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Bekliyor"),
                            ("sent", "Gönderildi"),
                            ("failed", "Başarısız"),
                            ("opened", "Açıldı"),
                            ("completed", "Tamamlandı"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("sms_message", models.TextField(blank=True)),
                ("sms_error", models.TextField(blank=True)),
                ("answers", models.JSONField(blank=True, default=dict)),
                (
                    "overall_score",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "guest",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="survey_invitations",
                        to="hotelcrm.guest",
                    ),
                ),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="survey_invitations",
                        to="hotelcrm.hotel",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_surveyinvitation",
                "ordering": ["-created_at"],
            },
        ),
    ]
