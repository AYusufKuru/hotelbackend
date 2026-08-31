"""
Seçili otel için Muhasebe modülü (ve ilişkili kayıtlar) test verisi.

Django admin veya shell yerine toplu üretim:
  py manage.py seed_accounting_test_data --hotel=DEMO
  py manage.py seed_accounting_test_data --hotel=DEMO --wipe

Tüm tohum kayıtları kod / numara / açıklama ile işaretlenir (--wipe ile silinir):
  - GL hesap kodları: TST* öneki
  - Fiş kodları: TST-FIS-...
  - Faturalar: TST-...-INV-...
  - Yevmiye açıklaması: [seed-accounting]
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hotelcrm.models import (
    BusinessPartner,
    DepartmentBudget,
    FixedAsset,
    GLAccount,
    Hotel,
    JournalEntry,
    OperationalInvoice,
    PurchaseOrder,
)
from hotelcrm.models.enums import (
    GLAccountType,
    InvoicePaymentStatus,
    InvoiceType,
    PurchaseOrderStatus,
)

SEED_TAG = "[seed-accounting]"
GL_PREFIX = "TST"
INV_PREFIX_FMT = "TST-{hotel}-INV-{n:05d}"
FIS_PREFIX_FMT = "TST-{hotel}-FIS-{n:04d}"


# TDHP-benzeri; kodlar otomatik TST ile birleştirilir (ör. TST100)
GL_CHART: tuple[tuple[str, str, str], ...] = (
    ("100", "Kasa", GLAccountType.ASSET),
    ("102", "Bankalar", GLAccountType.ASSET),
    ("120", "Alıcılar", GLAccountType.ASSET),
    ("191", "İndirilecek KDV", GLAccountType.ASSET),
    ("25501", "Demirbaşlar (Mobilya)", GLAccountType.ASSET),
    ("252", "Binalar", GLAccountType.ASSET),
    ("253", "Tesis, Makine ve Cihazlar", GLAccountType.ASSET),
    ("254", "Taşıtlar", GLAccountType.ASSET),
    ("260", "Haklar (Yazılım/Lisans)", GLAccountType.ASSET),
    ("257", "Birikmiş Amortismanlar (-)", GLAccountType.ASSET),
    ("268", "Birikmiş Amortismanlar — MO (-)", GLAccountType.ASSET),
    ("320", "Satıcılar", GLAccountType.LIABILITY),
    ("335", "Personele Borçlar", GLAccountType.LIABILITY),
    ("391", "Hesaplanan KDV", GLAccountType.LIABILITY),
    ("500", "Sermaye", GLAccountType.EQUITY),
    ("60001", "Konaklama Geliri", GLAccountType.REVENUE),
    ("60002", "F&B Geliri", GLAccountType.REVENUE),
    ("740", "Hizmet Üretim Maliyeti", GLAccountType.EXPENSE),
    ("74002", "Enerji / Su / Doğalgaz", GLAccountType.EXPENSE),
    ("760", "Pazarlama Gideri", GLAccountType.EXPENSE),
    ("770", "Genel Yönetim Gideri", GLAccountType.EXPENSE),
    ("78001", "Banka Komisyonu", GLAccountType.EXPENSE),
)


def d2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"))


def glc(suffix: str) -> str:
    return f"{GL_PREFIX}{suffix}"


class Command(BaseCommand):
    help = "Muhasebe: hesap planı, yevmiye, fatura, cari, demirbaş, bütçe, satınalma tohumu."

    def add_arguments(self, parser):
        parser.add_argument("--hotel", default="DEMO", help="Otel code (Hotel.code)")
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Önceki tohum kayıtlarını (TST* / [seed-accounting]) sil",
        )
        parser.add_argument(
            "--compact",
            action="store_true",
            help="Az cari/fatura/yevmiye (Vercel inceleme tohumu).",
        )

    def handle(self, *args, **options):
        code = str(options["hotel"]).strip()
        hotel = Hotel.objects.filter(code__iexact=code).first()
        if not hotel:
            self.stdout.write(self.style.ERROR(f"Otel bulunamadı: code={code!r}"))
            return

        if options["wipe"]:
            self._wipe(hotel)

        rnd = random.Random(2026514)
        today = timezone.localdate()
        compact = bool(options["compact"])

        with transaction.atomic():
            self._seed_gl(hotel, rnd)
            self._seed_partners(hotel, rnd, compact=compact)
            self._seed_fixed_assets(hotel, rnd, today, compact=compact)
            self._seed_budgets(hotel, today, compact=compact)
            self._seed_invoices(hotel, rnd, today, compact=compact)
            self._seed_purchase_orders(hotel, rnd, today, compact=compact)
            self._seed_journal(hotel, rnd, today, compact=compact)

        self.stdout.write(
            self.style.SUCCESS(
                f"Muhasebe tohumu tamam: {hotel.code} - GL hesap sayisi {len(GL_CHART)}, "
                "cari+demirbaş+fatura+PO+yevmiye eklendi. Uygulamada paketi yenileyin."
            )
        )

    def _wipe(self, hotel: Hotel) -> None:
        n_j = JournalEntry.objects.filter(hotel=hotel, description__contains=SEED_TAG).delete()[0]
        n_inv = OperationalInvoice.objects.filter(
            hotel=hotel, invoice_number__startswith=f"TST-{hotel.code}-"
        ).delete()[0]
        n_po = PurchaseOrder.objects.filter(hotel=hotel, display_code__startswith="TST-PO-").delete()[0]
        n_fa = FixedAsset.objects.filter(hotel=hotel, code__startswith="TST-FA-").delete()[0]
        n_bp = BusinessPartner.objects.filter(hotel=hotel, code__startswith="TST-").delete()[0]
        n_db = DepartmentBudget.objects.filter(
            hotel=hotel, display_code__startswith=f"TST-BDG-{hotel.code}-"
        ).delete()[0]
        n_gl = GLAccount.objects.filter(hotel=hotel, code__startswith=GL_PREFIX).delete()[0]
        self.stdout.write(
            f"Silindi: yevmiye={n_j}, fatura={n_inv}, PO={n_po}, demirbaş={n_fa}, "
            f"cari={n_bp}, bütçe={n_db}, GL={n_gl}"
        )

    def _seed_gl(self, hotel: Hotel, rnd: random.Random) -> list[GLAccount]:
        out: list[GLAccount] = []
        for suffix, name, typ in GL_CHART:
            code = glc(suffix)
            bal = Decimal("0")
            if typ == GLAccountType.ASSET and suffix not in ("257", "268"):
                bal = d2(Decimal(rnd.randint(5_000, 450_000)) + Decimal(rnd.random()) * 100)
            elif typ == GLAccountType.LIABILITY:
                bal = d2(Decimal(rnd.randint(2_000, 280_000)) + Decimal(rnd.random()) * 80)
            elif typ == GLAccountType.EQUITY:
                bal = d2(Decimal(rnd.randint(200_000, 2_000_000)))
            elif typ == GLAccountType.REVENUE:
                bal = d2(Decimal(rnd.randint(80_000, 1_200_000)))
            elif typ == GLAccountType.EXPENSE:
                bal = d2(Decimal(rnd.randint(10_000, 420_000)))
            obj, _ = GLAccount.objects.get_or_create(
                hotel=hotel,
                code=code,
                defaults={"name": f"{name} (test)", "account_type": typ, "balance": bal},
            )
            if not _:
                obj.name = f"{name} (test)"
                obj.account_type = typ
                obj.balance = bal
                obj.save(update_fields=["name", "account_type", "balance"])
            out.append(obj)
        return out

    def _seed_partners(self, hotel: Hotel, rnd: random.Random, *, compact: bool = False) -> None:
        TYPES = [
            ("customer", "120", "Misafir / Kurumsal"),
            ("supplier", "320", "Tedarikçi"),
            ("both", "120", "Çift taraflı"),
            ("staff", "335", "Personel"),
        ]
        cities = ("İstanbul", "Ankara", "İzmir", "Antalya", "Bursa")
        n_partners = 6 if compact else 28
        for i in range(n_partners):
            t, glsuf, label = TYPES[i % len(TYPES)]
            code = f"TST-P-{i + 1:03d}"
            title = f"{label} Demo {i + 1} — {rnd.choice(['A.Ş.', 'Ltd.', 'Şti.'])}"
            vkn = "".join(str(rnd.randint(0, 9)) for _ in range(10))
            BusinessPartner.objects.get_or_create(
                hotel=hotel,
                code=code,
                defaults={
                    "title": title,
                    "partner_type": t,
                    "tax_id": vkn,
                    "tax_office": rnd.choice(["Büyük Mükellefler", "Kızılbey", "Ulus"]),
                    "address": f"{rnd.choice(['Atatürk', 'Cumhuriyet', 'İnönü'])} Cd. No:{rnd.randint(1, 120)}",
                    "city": rnd.choice(cities),
                    "country": "Türkiye",
                    "contact_name": f"Yetkili {i + 1}",
                    "phone": f"0{rnd.randint(500, 599)} {rnd.randint(100, 999):03d} {rnd.randint(10, 99):02d} {rnd.randint(10, 99):02d}",
                    "email": f"tst-p{i + 1}@seed-accounting.test",
                    "opening_balance": d2(Decimal(rnd.randint(-50_000, 120_000))),
                    "credit_limit": d2(Decimal(rnd.randint(10_000, 500_000))),
                    "payment_term_days": rnd.choice([0, 7, 15, 30, 45]),
                    "iban": f"TR{''.join(str(rnd.randint(0, 9)) for _ in range(24))}",
                    "bank_name": rnd.choice(["Garanti BBVA", "İş Bankası", "Ziraat", "Yapı Kredi"]),
                    "gl_account_code": glc(glsuf),
                    "is_active": True,
                    "notes": f"Otomatik test carisi {SEED_TAG}",
                },
            )

    def _seed_fixed_assets(self, hotel: Hotel, rnd: random.Random, today: date, *, compact: bool = False) -> None:
        specs: list[tuple[str, str, str, Decimal, int]] = [
            ("building", "252", "Ana bina kabuk (demo)", Decimal("12500000"), 50),
            ("fixture", "25501", "Lobi mobilya takımı", Decimal("680000"), 5),
            ("it", "25501", "Sunucu ve network", Decimal("420000"), 4),
            ("kitchen", "25501", "Endüstriyel mutfak ekipmanı", Decimal("890000"), 5),
            ("vehicle", "254", "Misafir transfer minibüsü", Decimal("2100000"), 5),
            ("appliance", "25501", "Split klima hatları", Decimal("310000"), 8),
            ("machine", "253", "Çamaşırhane tambur kurutucu", Decimal("275000"), 10),
            ("intangible", "260", "PMS lisansı (3 yıl)", Decimal("180000"), 3),
        ]
        cats = [s[0] for s in specs]
        n_assets = 6 if compact else 22
        for i in range(n_assets):
            if i < len(specs):
                cat, glsuf, base_name, cost, life = specs[i]
            else:
                cat = rnd.choice(cats)
                glsuf = "25501"
                base_name = rnd.choice(["Konferans ses sistemi", "SPA sedye seti", "Kasa odası sayaç"])
                cost = Decimal(rnd.randint(15_000, 350_000))
                life = rnd.choice([4, 5, 8, 10])
            code = f"TST-FA-{i + 1:03d}"
            pd = today - timedelta(days=rnd.randint(120, 900))
            accum = d2(cost * Decimal(rnd.randint(5, 35)) / Decimal("100"))
            FixedAsset.objects.get_or_create(
                hotel=hotel,
                code=code,
                defaults={
                    "name": f"{base_name} #{i + 1}",
                    "category": cat,
                    "purchase_date": pd,
                    "cost": d2(cost),
                    "salvage_value": d2(cost * Decimal("0.02")),
                    "useful_life_years": life,
                    "method": "straight",
                    "annual_rate": Decimal("20.00") if life <= 5 else Decimal("10.00"),
                    "accumulated_depreciation": accum,
                    "last_depreciation_date": today - timedelta(days=rnd.randint(1, 40)),
                    "status": "active",
                    "gl_account_code": glc(glsuf),
                    "gl_depreciation_account": glc("268" if cat == "intangible" else "257"),
                    "supplier_name": rnd.choice(["Elektronik A.Ş.", "Otel Ekipman", "Mutfak Teknik"]),
                    "serial_no": f"SN-{uuid.uuid4().hex[:10].upper()}",
                    "location": rnd.choice(["Zemin kat", "Lobi", "Kat -1", "Teknik bodrum", "SPA"]),
                    "notes": f"Test demirbaş {SEED_TAG}",
                },
            )

    def _seed_budgets(self, hotel: Hotel, today: date, *, compact: bool = False) -> None:
        year = today.year
        depts = [
            "Housekeeping",
            "Ön Büro",
            "F&B Mutfak",
            "F&B Servis",
            "Teknik",
            "İnsan Kaynakları",
            "Satış",
            "SPA",
            "Güvenlik",
            "Muhasebe",
        ]
        if compact:
            depts = depts[:4]
        for i, name in enumerate(depts):
            b = Decimal(180_000 + i * 45_000)
            a = d2(b * Decimal(random.Random(2026 + i).uniform(0.72, 1.08)))
            DepartmentBudget.objects.get_or_create(
                hotel=hotel,
                display_code=f"TST-BDG-{hotel.code}-{year}-{i + 1:02d}",
                defaults={
                    "department_name": name,
                    "fiscal_year": year,
                    "budget_amount": d2(b),
                    "actual_amount": a,
                },
            )

    def _invoice_notes_json(self, brut: Decimal, kdv_rate: int) -> str:
        net = d2(brut / (Decimal("1") + Decimal(kdv_rate) / Decimal("100")))
        kdv = d2(brut - net)
        payload = {
            "lines": [
                {
                    "desc": "Demo kalem",
                    "qty": 1,
                    "unitPrice": float(net),
                    "kdvRate": kdv_rate,
                }
            ],
            "kdvTotal": float(kdv),
            "netTotal": float(net),
            "freeNote": f"Otomatik fatura {SEED_TAG}",
        }
        return json.dumps(payload, ensure_ascii=False)

    def _seed_invoices(self, hotel: Hotel, rnd: random.Random, today: date, *, compact: bool = False) -> None:
        sale_scenarios = [
            ("KONAK_OTEL", 10),
            ("FB_REST", 10),
            ("SPA_WELL", 20),
            ("BANQUET", 10),
            ("MINIBAR", 10),
            ("LAUNDRY", 10),
            ("B2B_ACENTE", 10),
        ]
        purch_scenarios = [
            ("TEDARIKCI", 20),
            ("ENERJI", 20),
            ("TEMIZLIK_MAL", 20),
            ("YAZILIM_SAAS", 20),
            ("POS_KOMIS", 20),
        ]
        refund_scenarios = [("IADE_KONAK", 10), ("IADE_FB", 10)]
        customers = [
            "Demo Turizm A.Ş.",
            "Global Rezervasyon Ltd.",
            "Sunset Travel",
            "Anadolu Holding",
            "Deniz Faturası Ltd.",
        ]
        suppliers = [
            "Enerji Tedarik A.Ş.",
            "Temizlik Kimya San.",
            "Gıda Toptan Ltd.",
            "Bulut Yazılım A.Ş.",
            "Bank POS Hizmet",
        ]

        n = 0
        n_sale = 4 if compact else 22
        n_purch = 3 if compact else 20
        n_refund = 1 if compact else 5
        for _ in range(n_sale):
            cat, kdv_p = rnd.choice(sale_scenarios)
            brut = Decimal(rnd.randint(2_000, 180_000))
            paid = brut if rnd.random() < 0.55 else d2(brut * Decimal(rnd.randint(0, 80)) / Decimal("100"))
            st = InvoicePaymentStatus.PAID if paid >= brut - Decimal("0.02") else InvoicePaymentStatus.UNPAID
            n += 1
            inv_no = INV_PREFIX_FMT.format(hotel=hotel.code, n=n)
            OperationalInvoice.objects.get_or_create(
                hotel=hotel,
                invoice_number=inv_no,
                defaults={
                    "invoice_type": InvoiceType.SALE,
                    "category": cat,
                    "customer_name": rnd.choice(customers),
                    "customer_address": "Bağdat Cd. İstanbul",
                    "customer_email": f"sale-{n}@seed.test",
                    "amount": d2(brut),
                    "invoice_date": today - timedelta(days=rnd.randint(0, 120)),
                    "due_date": today + timedelta(days=rnd.randint(7, 45)),
                    "payment_status": st,
                    "paid_amount": d2(paid),
                    "paid_at": (today - timedelta(days=rnd.randint(0, 15))) if st == InvoicePaymentStatus.PAID else None,
                    "tax_id": "".join(str(rnd.randint(0, 9)) for _ in range(10)),
                    "currency": "TRY",
                    "notes": self._invoice_notes_json(d2(brut), kdv_p),
                },
            )

        for _ in range(n_purch):
            cat, kdv_p = rnd.choice(purch_scenarios)
            brut = Decimal(rnd.randint(1_500, 95_000))
            paid = brut if rnd.random() < 0.5 else Decimal("0")
            st = InvoicePaymentStatus.PAID if paid >= brut - Decimal("0.02") else InvoicePaymentStatus.UNPAID
            n += 1
            inv_no = INV_PREFIX_FMT.format(hotel=hotel.code, n=n)
            OperationalInvoice.objects.get_or_create(
                hotel=hotel,
                invoice_number=inv_no,
                defaults={
                    "invoice_type": InvoiceType.PURCHASE,
                    "category": cat,
                    "customer_name": rnd.choice(suppliers),
                    "amount": d2(brut),
                    "invoice_date": today - timedelta(days=rnd.randint(0, 90)),
                    "due_date": today + timedelta(days=rnd.randint(5, 60)),
                    "payment_status": st,
                    "paid_amount": d2(paid),
                    "paid_at": (today - timedelta(days=rnd.randint(0, 20))) if st == InvoicePaymentStatus.PAID else None,
                    "tax_id": "".join(str(rnd.randint(0, 9)) for _ in range(10)),
                    "currency": "TRY",
                    "notes": self._invoice_notes_json(d2(brut), kdv_p),
                },
            )

        for _ in range(n_refund):
            cat, kdv_p = rnd.choice(refund_scenarios)
            brut = Decimal(rnd.randint(500, 25_000))
            n += 1
            inv_no = INV_PREFIX_FMT.format(hotel=hotel.code, n=n)
            OperationalInvoice.objects.get_or_create(
                hotel=hotel,
                invoice_number=inv_no,
                defaults={
                    "invoice_type": InvoiceType.REFUND,
                    "category": cat,
                    "customer_name": rnd.choice(customers),
                    "amount": d2(brut),
                    "invoice_date": today - timedelta(days=rnd.randint(0, 45)),
                    "payment_status": InvoicePaymentStatus.PAID,
                    "paid_amount": d2(brut),
                    "paid_at": today - timedelta(days=rnd.randint(0, 10)),
                    "tax_id": "",
                    "currency": "TRY",
                    "notes": self._invoice_notes_json(d2(brut), kdv_p),
                },
            )

    def _seed_purchase_orders(self, hotel: Hotel, rnd: random.Random, today: date, *, compact: bool = False) -> None:
        statuses = list(PurchaseOrderStatus)
        cats = ("Gıda & İçecek", "Temizlik", "Tekstil", "Teknoloji", "Ofis", "Bakım & Onarım")
        items = (
            "Kuru gıda partisi",
            "Temizlik kimyasalı",
            "Çarşaf & havlu seti",
            "POS sarf malzemesi",
            "Büro kağıt & toner",
            "Havalandırma filtresi",
        )
        suppliers = ("Gıda Ltd.", "Temizlik A.Ş.", "Tekstil San.", "Teknoloji A.Ş.", "Ofis Malz. Ltd.")
        n_po = 4 if compact else 18
        for i in range(n_po):
            PurchaseOrder.objects.get_or_create(
                hotel=hotel,
                display_code=f"TST-PO-{hotel.code}-{i + 1:03d}",
                defaults={
                    "item_description": f"{rnd.choice(items)} — parti {i + 1}",
                    "supplier_name": rnd.choice(suppliers),
                    "category": rnd.choice(cats),
                    "amount": d2(Decimal(rnd.randint(3_000, 120_000))),
                    "order_date": today - timedelta(days=rnd.randint(0, 60)),
                    "status": rnd.choice(statuses),
                    "supplier_tax_id": "".join(str(rnd.randint(0, 9)) for _ in range(10)),
                    "supplier_tax_office": rnd.choice(["Maslak", "Çankaya", "Konak"]),
                },
            )

    def _seed_journal(
        self,
        hotel: Hotel,
        rnd: random.Random,
        today: date,
        *,
        compact: bool = False,
    ) -> None:
        if JournalEntry.objects.filter(hotel=hotel, description__contains=SEED_TAG).exists():
            return
        # scenarios with balanced amounts
        specs = [
            ("Nakit tahsilat", [("100", "D", "12000"), ("120", "C", "12000")]),
            ("Banka tahsilat", [("102", "D", "35000"), ("120", "C", "35000")]),
            ("Konaklama satışı", [("120", "D", "11000"), ("60001", "C", "10000"), ("391", "C", "1000")]),
            ("F&B satışı", [("120", "D", "5500"), ("60002", "C", "5000"), ("391", "C", "500")]),
            ("Mal alımı", [("740", "D", "20000"), ("191", "D", "4000"), ("320", "C", "24000")]),
            ("Enerji", [("74002", "D", "8000"), ("191", "D", "1600"), ("320", "C", "9600")]),
            ("Pazarlama", [("760", "D", "5000"), ("191", "D", "1000"), ("320", "C", "6000")]),
            ("Genel yönetim", [("770", "D", "12500"), ("320", "C", "12500")]),
            ("Banka komisyonu", [("78001", "D", "400"), ("191", "D", "80"), ("320", "C", "480")]),
            ("Personel borçlanması", [("770", "D", "9000"), ("335", "C", "9000")]),
        ]
        n_fis = 8 if compact else 34
        for fid in range(1, n_fis + 1):
            title, raw_lines = rnd.choice(specs)
            entry_date = today - timedelta(days=rnd.randint(0, 130))
            fis_no = FIS_PREFIX_FMT.format(hotel=hotel.code, n=fid)
            desc = f"{title} {SEED_TAG}"
            for suf, side, amt_s in raw_lines:
                amt = Decimal(amt_s)
                JournalEntry.objects.create(
                    hotel=hotel,
                    display_code=fis_no,
                    entry_date=entry_date,
                    description=desc,
                    debit_amount=amt if side == "D" else None,
                    credit_amount=amt if side == "C" else None,
                    account_code=glc(suf),
                )

