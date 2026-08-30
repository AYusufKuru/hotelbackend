from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0031_user_module_grant"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="hotel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="audit_logs",
                to="hotelcrm.hotel",
            ),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="target_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="audit_logs_about",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="target_user_label",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="ip_address",
            field=models.CharField(blank=True, max_length=45),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="entity_type",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="entity_id",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["-occurred_at"], name="hotelcrm_au_occurre_0a8f2d_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["hotel", "-occurred_at"], name="hotelcrm_au_hotel_i_4e2c91_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user", "-occurred_at"], name="hotelcrm_au_user_id_7b3a44_idx"),
        ),
    ]
