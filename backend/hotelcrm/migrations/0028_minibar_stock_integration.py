"""Mini bar–stok entegrasyonu.

- InventoryItem.usage_area choices'a `minibar` eklenir.
- MinibarChargeLine.inventory_item FK eklenir (oda tüketimi otomatik stoktan düşer).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0027_fnb_event_module_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inventoryitem",
            name="usage_area",
            field=models.CharField(
                choices=[
                    ("stock_only", "Sadece stok"),
                    ("restaurant", "Restoran (POS menüsü)"),
                    ("minibar", "Mini Bar (oda tüketim katalogu)"),
                ],
                default="stock_only",
                help_text=(
                    "Restoran seçilirse ürün Stok tanımından POS menüsünde listelenir. "
                    "Mini Bar seçilirse mini bar katalogunda listelenir ve oda tüketiminde stoktan düşer."
                ),
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="minibarchargeline",
            name="inventory_item",
            field=models.ForeignKey(
                blank=True,
                help_text="Mini bar fiş satırı stok kalemiyle eşleşir; eski ürün kataloğu opsiyoneldir.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="minibar_charge_lines",
                to="hotelcrm.inventoryitem",
            ),
        ),
    ]
