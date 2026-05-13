# Generated for accounting module overhaul — OperationalInvoice zenginleştirildi.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotelcrm', '0018_travel_agency_and_commercial_contract_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='operationalinvoice',
            name='customer_address',
            field=models.CharField(blank=True, default='', max_length=512),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='customer_email',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='paid_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='paid_at',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='currency',
            field=models.CharField(default='TRY', max_length=8),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='is_cancelled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='operationalinvoice',
            name='cancel_reason',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
