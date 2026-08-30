"""Stok–restoran POS: envanter usage_area, sale_price; sipariş satırında inventory_item."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0025_stock_module_extensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="usage_area",
            field=models.CharField(
                choices=[
                    ("stock_only", "Sadece stok"),
                    ("restaurant", "Restoran (POS menüsü)"),
                ],
                default="stock_only",
                help_text="Restoran seçilirse ürün Stok tanımından POS menüsünde listelenir.",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="sale_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Restoran satış fiyatı. Boşsa POS’da birim maliyet gösterilir.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="restaurantorderline",
            name="inventory_item",
            field=models.ForeignKey(
                blank=True,
                help_text="POS satırı stok kalemiyle eşleşir; menü kalemi tutulmaz.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="restaurant_order_lines",
                to="hotelcrm.inventoryitem",
            ),
        ),
    ]
