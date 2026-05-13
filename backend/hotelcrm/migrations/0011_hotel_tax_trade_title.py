from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0010_inventoryitem_warehouse"),
    ]

    operations = [
        migrations.AddField(
            model_name="hotel",
            name="tax_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Otel VKN (10) veya yetkili TCKN (11)",
                max_length=11,
            ),
        ),
        migrations.AddField(
            model_name="hotel",
            name="trade_title",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Ticari unvan (fatura üst bilgisi)",
                max_length=255,
            ),
        ),
    ]
