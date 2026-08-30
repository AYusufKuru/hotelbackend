import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0036_merge_20260705_1330"),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupBookingMember",
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
                ("full_name", models.CharField(max_length=255)),
                ("phone", models.CharField(blank=True, max_length=64)),
                ("sequence", models.PositiveSmallIntegerField(default=0)),
                ("is_leader", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                (
                    "group_booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="hotelcrm.groupbooking",
                    ),
                ),
                (
                    "reservation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="group_booking_member_links",
                        to="hotelcrm.reservation",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="group_booking_members",
                        to="hotelcrm.room",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_groupbookingmember",
                "ordering": ["sequence", "id"],
            },
        ),
    ]
