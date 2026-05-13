import django.db.models.deletion
from django.db import migrations, models


def forwards_userrole_hotel(apps, schema_editor):
    UserRole = apps.get_model("hotelcrm", "UserRole")
    Hotel = apps.get_model("hotelcrm", "Hotel")
    hotel = Hotel.objects.order_by("pk").first()
    if hotel:
        UserRole.objects.filter(hotel__isnull=True).update(hotel_id=hotel.pk)
    else:
        UserRole.objects.filter(hotel__isnull=True).delete()


def forwards_userrole_dedupe(apps, schema_editor):
    UserRole = apps.get_model("hotelcrm", "UserRole")
    seen: set[tuple[int, int]] = set()
    for ur in UserRole.objects.order_by("pk"):
        uid, hid = ur.user_id, ur.hotel_id
        if hid is None:
            ur.delete()
            continue
        key = (uid, hid)
        if key in seen:
            ur.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0013_staff_contact_and_absence"),
    ]

    operations = [
        migrations.CreateModel(
            name="HotelModuleOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module_id", models.CharField(max_length=64)),
                ("is_enabled", models.BooleanField(default=True)),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="module_overrides",
                        to="hotelcrm.hotel",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_hotelmoduleoverride",
                "unique_together": {("hotel", "module_id")},
            },
        ),
        migrations.AlterUniqueTogether(
            name="userrole",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="userrole",
            name="hotel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_roles",
                to="hotelcrm.hotel",
            ),
        ),
        migrations.RunPython(forwards_userrole_hotel, migrations.RunPython.noop),
        migrations.RunPython(forwards_userrole_dedupe, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.UniqueConstraint(
                fields=("user", "hotel"),
                name="hotelcrm_userrole_user_hotel_uniq",
            ),
        ),
        migrations.AlterField(
            model_name="userrole",
            name="hotel",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_roles",
                to="hotelcrm.hotel",
            ),
        ),
    ]
