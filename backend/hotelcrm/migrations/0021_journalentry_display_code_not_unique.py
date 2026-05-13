# JournalEntry.display_code — çok satırlı fiş için unique kaldırıldı

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0020_fixed_asset_and_business_partner"),
    ]

    operations = [
        migrations.AlterField(
            model_name="journalentry",
            name="display_code",
            field=models.CharField(blank=True, db_index=True, max_length=32, null=True),
        ),
    ]
