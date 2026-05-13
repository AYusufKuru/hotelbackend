# Sabit kıymet (FixedAsset) ve cari kart (BusinessPartner) modelleri.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotelcrm', '0019_operational_invoice_accounting_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='FixedAsset',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=32)),
                ('name', models.CharField(max_length=255)),
                ('category', models.CharField(
                    choices=[
                        ('building', 'Bina'),
                        ('land', 'Arazi / Arsa'),
                        ('machine', 'Tesis / Makine / Cihaz'),
                        ('vehicle', 'Taşıt'),
                        ('fixture', 'Demirbaş — Mobilya'),
                        ('it', 'Bilgisayar / IT Donanım'),
                        ('kitchen', 'Mutfak / F&B Demirbaşı'),
                        ('appliance', 'Beyaz Eşya / Klima'),
                        ('intangible', 'Maddi Olmayan (Yazılım/Lisans)'),
                        ('other', 'Diğer Maddi Duran Varlık'),
                    ],
                    default='fixture',
                    max_length=32,
                )),
                ('purchase_date', models.DateField()),
                ('cost', models.DecimalField(decimal_places=2, max_digits=14)),
                ('salvage_value', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('useful_life_years', models.PositiveSmallIntegerField(default=5)),
                ('method', models.CharField(
                    choices=[
                        ('straight', 'Normal (Eşit)'),
                        ('declining_balance', 'Azalan Bakiyeler'),
                    ],
                    default='straight',
                    max_length=24,
                )),
                ('annual_rate', models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ('accumulated_depreciation', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('last_depreciation_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('active', 'Aktif'),
                        ('sold', 'Satıldı'),
                        ('disposed', 'Hurdaya Ayrıldı'),
                        ('idle', 'Atıl'),
                    ],
                    default='active',
                    max_length=16,
                )),
                ('gl_account_code', models.CharField(default='255', max_length=32)),
                ('gl_depreciation_account', models.CharField(default='257', max_length=32)),
                ('supplier_name', models.CharField(blank=True, default='', max_length=255)),
                ('serial_no', models.CharField(blank=True, default='', max_length=128)),
                ('location', models.CharField(blank=True, default='', max_length=255)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('hotel', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fixed_assets',
                    to='hotelcrm.hotel',
                )),
            ],
            options={
                'db_table': 'hotelcrm_fixedasset',
                'unique_together': {('hotel', 'code')},
            },
        ),
        migrations.CreateModel(
            name='BusinessPartner',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=32)),
                ('title', models.CharField(max_length=255)),
                ('partner_type', models.CharField(
                    choices=[
                        ('customer', 'Müşteri'),
                        ('supplier', 'Tedarikçi'),
                        ('both', 'Müşteri & Tedarikçi'),
                        ('staff', 'Personel'),
                        ('partner', 'Ortak'),
                        ('other', 'Diğer'),
                    ],
                    default='customer',
                    max_length=16,
                )),
                ('tax_id', models.CharField(blank=True, default='', max_length=32)),
                ('tax_office', models.CharField(blank=True, default='', max_length=128)),
                ('address', models.CharField(blank=True, default='', max_length=512)),
                ('city', models.CharField(blank=True, default='', max_length=64)),
                ('country', models.CharField(blank=True, default='Türkiye', max_length=64)),
                ('contact_name', models.CharField(blank=True, default='', max_length=128)),
                ('phone', models.CharField(blank=True, default='', max_length=32)),
                ('email', models.CharField(blank=True, default='', max_length=128)),
                ('opening_balance', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('credit_limit', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('payment_term_days', models.PositiveSmallIntegerField(default=30)),
                ('iban', models.CharField(blank=True, default='', max_length=64)),
                ('bank_name', models.CharField(blank=True, default='', max_length=128)),
                ('gl_account_code', models.CharField(default='120', max_length=32)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hotel', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='business_partners',
                    to='hotelcrm.hotel',
                )),
            ],
            options={
                'db_table': 'hotelcrm_businesspartner',
                'ordering': ['title'],
                'unique_together': {('hotel', 'code')},
            },
        ),
    ]
