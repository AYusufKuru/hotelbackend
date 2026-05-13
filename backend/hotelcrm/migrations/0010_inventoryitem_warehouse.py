from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0009_roomtype_bed_counts"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="warehouse",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Depo / lokasyon (örn. Ana depo, Mutfak, HK)",
                max_length=64,
            ),
        ),
    ]
