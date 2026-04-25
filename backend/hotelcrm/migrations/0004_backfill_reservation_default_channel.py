from django.db import migrations


def assign_default_channel(apps, schema_editor):
    Channel = apps.get_model("hotelcrm", "Channel")
    Reservation = apps.get_model("hotelcrm", "Reservation")
    for res in Reservation.objects.filter(channel__isnull=True):
        hotel_id = res.hotel_id
        ch = Channel.objects.filter(hotel_id=hotel_id, name="Direkt").first()
        if not ch:
            ch = Channel.objects.create(
                hotel_id=hotel_id,
                name="Direkt",
                code="DIRECT",
            )
        res.channel_id = ch.id
        res.save(update_fields=["channel"])


def assign_default_channel_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0003_hotel_reservation_sequence_and_backfill"),
    ]

    operations = [
        migrations.RunPython(
            assign_default_channel,
            assign_default_channel_reverse,
        ),
    ]
