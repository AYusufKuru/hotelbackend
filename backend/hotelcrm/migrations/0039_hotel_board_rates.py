from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0038_seed_all_module_permissions_and_ops_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="hotel",
            name="board_rate_ai",
            field=models.DecimalField(
                decimal_places=2,
                default=750,
                help_text="Her şey dahil (AI) kişi başı gece farkı (₺)",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="hotel",
            name="board_rate_bb",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Oda kahvaltı (BB) kişi başı gece farkı (₺)",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="hotel",
            name="board_rate_fb",
            field=models.DecimalField(
                decimal_places=2,
                default=550,
                help_text="Tam pansiyon (FB) kişi başı gece farkı (₺)",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="hotel",
            name="board_rate_hb",
            field=models.DecimalField(
                decimal_places=2,
                default=350,
                help_text="Yarım pansiyon (HB) kişi başı gece farkı (₺)",
                max_digits=12,
            ),
        ),
        migrations.AlterField(
            model_name="reservation",
            name="board_basis",
            field=models.CharField(
                blank=True,
                choices=[("BB", "BB"), ("HB", "HB"), ("FB", "FB"), ("AI", "AI")],
                max_length=8,
            ),
        ),
    ]
