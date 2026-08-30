"""Stok modülü genişletmesi.

* `InventoryItem`a SKU, barkod, tedarikçi, maks. miktar, son satış/tazeleme tarihi,
  raf, son giriş tarihi, notlar ve arşiv bayrağı eklenir.
* `StockMovement` modeli (giriş, çıkış, transfer, sayım, fire, iade) eklenir.
* `StockCountSession` ve `StockCountLine` sayım modülü için eklenir.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0024_hotel_recruitment"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="max_quantity",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Yeniden sipariş tavanı; boşsa min_quantity * 4 kabul edilir.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="sku",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="barcode",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="supplier_name",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="location_in_warehouse",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Raf / lokasyon (örn. R3-Ü2)",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="expiry_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="last_restocked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="StockMovement",
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
                (
                    "movement_type",
                    models.CharField(
                        choices=[
                            ("in", "Giriş"),
                            ("out", "Çıkış"),
                            ("transfer", "Transfer"),
                            ("count", "Sayım düzeltmesi"),
                            ("waste", "Fire / zayi"),
                            ("return", "Tedarikçi iadesi"),
                        ],
                        default="in",
                        max_length=16,
                    ),
                ),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Pozitif miktar; yön movement_type ile belirlenir.",
                        max_digits=12,
                    ),
                ),
                (
                    "unit_cost",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=12, null=True,
                    ),
                ),
                ("from_warehouse", models.CharField(blank=True, default="", max_length=64)),
                ("to_warehouse", models.CharField(blank=True, default="", max_length=64)),
                ("reason", models.CharField(blank=True, default="", max_length=128)),
                (
                    "reference_no",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Satın alma emri no, fatura no, vb.",
                        max_length=64,
                    ),
                ),
                ("staff_name", models.CharField(blank=True, default="", max_length=128)),
                ("business_date", models.DateField()),
                ("note", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_movements",
                        to="hotelcrm.hotel",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_movements",
                        to="hotelcrm.inventoryitem",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_stockmovement",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="StockCountSession",
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
                ("display_code", models.CharField(blank=True, default="", max_length=32)),
                ("title", models.CharField(default="Stok sayımı", max_length=128)),
                ("warehouse", models.CharField(blank=True, default="", max_length=64)),
                ("started_on", models.DateField()),
                ("closed_on", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Açık"),
                            ("closed", "Tamamlandı"),
                            ("cancelled", "İptal"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("note", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_count_sessions",
                        to="hotelcrm.hotel",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_stockcountsession",
                "ordering": ["-started_on", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="StockCountLine",
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
                ("expected_qty", models.DecimalField(decimal_places=2, max_digits=12)),
                ("counted_qty", models.DecimalField(decimal_places=2, max_digits=12)),
                ("note", models.CharField(blank=True, default="", max_length=128)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="count_lines",
                        to="hotelcrm.inventoryitem",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="hotelcrm.stockcountsession",
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_stockcountline",
            },
        ),
    ]
