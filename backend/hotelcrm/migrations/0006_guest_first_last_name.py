# Misafir: full_name → first_name + last_name

from django.db import migrations, models


def forwards_split_full_name(apps, schema_editor):
    Guest = apps.get_model("hotelcrm", "Guest")
    for g in Guest.objects.all().iterator():
        raw = (getattr(g, "full_name", None) or "").strip()
        if not raw:
            Guest.objects.filter(pk=g.pk).update(first_name="", last_name="")
            continue
        parts = raw.split(None, 1)
        fn = (parts[0] if parts else "")[:127]
        ln = (parts[1].strip() if len(parts) > 1 else "")[:127]
        Guest.objects.filter(pk=g.pk).update(first_name=fn, last_name=ln)


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0005_hotel_address_hotel_latitude_hotel_longitude_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="guest",
            name="first_name",
            field=models.CharField(blank=True, default="", max_length=127),
        ),
        migrations.AddField(
            model_name="guest",
            name="last_name",
            field=models.CharField(blank=True, default="", max_length=127),
        ),
        migrations.RunPython(forwards_split_full_name, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="guest",
            name="full_name",
        ),
    ]
