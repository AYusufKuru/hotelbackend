from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0011_hotel_tax_trade_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="supplier_tax_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Satıcı VKN (10 hane) veya TCKN (11 hane)",
                max_length=11,
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="supplier_tax_office",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Vergi dairesi (kurumsal satıcı için)",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="operational_invoice_id",
            field=models.UUIDField(
                blank=True,
                help_text="Oluşturulan alım faturası (operationalinvoice) kaydı",
                null=True,
            ),
        ),
    ]
