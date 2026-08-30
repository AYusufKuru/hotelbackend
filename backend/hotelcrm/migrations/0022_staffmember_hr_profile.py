from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0021_journalentry_display_code_not_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffmember",
            name="hr_profile",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
