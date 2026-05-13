import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0006_guest_first_last_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservationOccupant",
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
                ("is_primary", models.BooleanField(default=False)),
                ("sequence", models.PositiveSmallIntegerField(default=0)),
                (
                    "guest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservation_occupant_links",
                        to="hotelcrm.guest",
                    ),
                ),
                (
                    "reservation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="occupants",
                        to="hotelcrm.reservation",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_reservationoccupant",
                "ordering": ["sequence", "id"],
            },
        ),
    ]
