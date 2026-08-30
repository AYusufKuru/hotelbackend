import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hotelcrm", "0030_survey_sms"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserModuleGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module_id", models.CharField(max_length=64)),
                (
                    "hotel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_module_grants",
                        to="hotelcrm.hotel",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="module_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "hotelcrm_usermodulegrant",
            },
        ),
        migrations.AddConstraint(
            model_name="usermodulegrant",
            constraint=models.UniqueConstraint(
                fields=("user", "hotel", "module_id"),
                name="hotelcrm_usermodulegrant_uniq",
            ),
        ),
    ]
