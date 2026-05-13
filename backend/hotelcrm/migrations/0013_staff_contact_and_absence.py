import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0012_purchaseorder_supplier_tax_invoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffmember",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="staffmember",
            name="national_id",
            field=models.CharField(blank=True, max_length=11),
        ),
        migrations.CreateModel(
            name="StaffAbsenceReport",
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
                ("absence_date", models.DateField()),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("sick", "Hastalık / rapor"),
                            ("annual", "Yıllık izin"),
                            ("unexcused", "Mazeretsiz devamsızlık"),
                            ("excused", "Mazeretli devamsızlık"),
                            ("other", "Diğer"),
                        ],
                        max_length=32,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staff_absence_reports",
                        to="hotelcrm.hotel",
                    ),
                ),
                (
                    "staff_member",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="absence_reports",
                        to="hotelcrm.staffmember",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_staffabsencereport",
                "ordering": ("-absence_date", "-created_at"),
            },
        ),
    ]
