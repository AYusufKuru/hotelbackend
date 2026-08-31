"""Stok modülü için demo verisi.

Bir otel için tipik otel envanteri (temizlik, banyo amenity, tekstil, ofis,
gıda dışı sarf vb.), birden çok depo, tedarikçi, son kullanma tarihi ve
örnek stok hareketleri oluşturur. `--wipe` ile mevcut stok verileri silinip
yeniden üretilir.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone

from hotelcrm import stock_signals
from hotelcrm.models import (
    Hotel,
    InventoryItem,
    InventoryStockLot,
    StockCountLine,
    StockCountSession,
    StockMovement,
)


SEED_ITEMS = [
    # (name, category, warehouse, unit, qty, min, max, cost, sku, supplier, shelf, days_to_expiry)
    ("Banyo havlusu (büyük)", "Tekstil", "Çamaşırhane", "adet", 320, 80, 400, 145, "TX-TWL-L", "Tekstil San.", "R1-Ü1", None),
    ("Banyo havlusu (küçük)", "Tekstil", "Çamaşırhane", "adet", 410, 100, 500, 75, "TX-TWL-S", "Tekstil San.", "R1-Ü2", None),
    ("Yatak çarşafı (king)", "Tekstil", "Çamaşırhane", "adet", 180, 60, 240, 240, "TX-SHT-K", "Tekstil San.", "R2-Ü1", None),
    ("Yastık kılıfı", "Tekstil", "Çamaşırhane", "adet", 540, 120, 600, 60, "TX-PIL-C", "Tekstil San.", "R2-Ü3", None),
    ("Şampuan 30ml", "Banyo amenity", "Ana depo", "adet", 1200, 400, 2000, 8.5, "AM-SH-30", "Amenity Ltd.", "A1-Ü1", 540),
    ("Saç kremi 30ml", "Banyo amenity", "Ana depo", "adet", 920, 400, 2000, 8.5, "AM-CD-30", "Amenity Ltd.", "A1-Ü2", 540),
    ("Duş jeli 30ml", "Banyo amenity", "Ana depo", "adet", 60, 400, 2000, 8.5, "AM-SG-30", "Amenity Ltd.", "A1-Ü3", 540),
    ("Sabun 25g", "Banyo amenity", "Ana depo", "adet", 1800, 600, 2500, 5.0, "AM-SO-25", "Amenity Ltd.", "A1-Ü4", 720),
    ("Tuvalet kağıdı 200 yp", "Sarf", "Ana depo", "rulo", 720, 300, 1000, 6.5, "SF-TP-200", "Gıda Ltd.", "B1-Ü1", None),
    ("Kâğıt havlu 80 yp", "Sarf", "Mutfak", "rulo", 240, 120, 400, 14.0, "SF-PT-80", "Gıda Ltd.", "B1-Ü2", None),
    ("Çamaşır deterjanı 5L", "Temizlik", "Çamaşırhane", "L", 80, 40, 120, 165, "TM-LD-5L", "Temizlik A.Ş.", "C1-Ü1", 720),
    ("Genel temizleyici 5L", "Temizlik", "Ana depo", "L", 32, 30, 80, 95, "TM-GC-5L", "Temizlik A.Ş.", "C1-Ü2", 720),
    ("Cam temizleyici 750ml", "Temizlik", "Ana depo", "şişe", 28, 30, 100, 38, "TM-WC-750", "Temizlik A.Ş.", "C1-Ü3", 540),
    ("Klor 5L", "Temizlik", "Teknik", "L", 18, 12, 40, 145, "TM-CL-5L", "Temizlik A.Ş.", "C2-Ü1", 540),
    ("Süt 1L", "Gıda dışı", "Mutfak", "L", 35, 40, 80, 28, "GD-MK-1L", "Gıda Ltd.", "M1-Ü1", 12),
    ("Kahve çekirdek 1kg", "Gıda dışı", "Mutfak", "kg", 22, 12, 30, 685, "GD-CF-1K", "Gıda Ltd.", "M1-Ü2", 240),
    ("Çay (siyah) 1kg", "Gıda dışı", "Mutfak", "kg", 14, 8, 20, 240, "GD-TE-1K", "Gıda Ltd.", "M1-Ü3", 365),
    ("Ampul LED 9W", "Bakım", "Teknik", "adet", 60, 30, 100, 38, "TC-LED-9", "Teknoloji A.Ş.", "T1-Ü1", None),
    ("Pil AA (paket 4)", "Bakım", "Teknik", "paket", 24, 20, 60, 55, "TC-BAT-AA", "Teknoloji A.Ş.", "T1-Ü2", None),
    ("Kartuş HP 305", "Ofis", "Ön büro", "adet", 6, 4, 12, 985, "OF-HP-305", "Ofis Malz. Ltd.", "O1-Ü1", None),
    ("A4 fotokopi kâğıdı", "Ofis", "Ön büro", "paket", 18, 10, 30, 220, "OF-PA-A4", "Ofis Malz. Ltd.", "O1-Ü2", None),
    ("Diş fırçası seti", "Banyo amenity", "Ana depo", "adet", 320, 200, 600, 22, "AM-TB-01", "Amenity Ltd.", "A2-Ü1", 720),
    ("Terlik (tek kullanım)", "Banyo amenity", "Ana depo", "çift", 460, 200, 800, 14, "AM-SL-01", "Amenity Ltd.", "A2-Ü2", None),
    ("Masaj yağı 250ml", "Sarf", "SPA", "şişe", 18, 12, 30, 285, "SF-MO-250", "Amenity Ltd.", "S1-Ü1", 365),
]


class Command(BaseCommand):
    help = "Stok modülü için demo veri (envanter + hareketler + sayım örneği) üretir."

    def add_arguments(self, parser):
        parser.add_argument("--hotel", default="DEMO", help="Otel adı veya kodu.")
        parser.add_argument("--wipe", action="store_true", help="Mevcut stok verisini sil ve yeniden üret.")
        parser.add_argument("--compact", action="store_true", help="Az ürün ve hareket (Vercel).")

    @transaction.atomic
    def handle(self, *args, **opts):
        key = (opts["hotel"] or "").strip()
        hotel = (
            Hotel.objects.filter(code__iexact=key).first()
            or Hotel.objects.filter(name__iexact=key).first()
            or Hotel.objects.first()
        )
        if not hotel:
            self.stderr.write(self.style.ERROR(
                "Otel bulunamadı; önce seed_demo_hotel çalıştırın."
            ))
            return

        if opts["wipe"]:
            StockMovement.objects.filter(hotel=hotel).delete()
            StockCountLine.objects.filter(session__hotel=hotel).delete()
            StockCountSession.objects.filter(hotel=hotel).delete()
            InventoryStockLot.objects.filter(hotel=hotel).delete()
            InventoryItem.objects.filter(hotel=hotel).delete()

        post_save.disconnect(
            stock_signals._on_stock_movement_saved,
            sender=StockMovement,
        )
        post_save.disconnect(
            stock_signals._on_inventory_item_initial_lot,
            sender=InventoryItem,
        )
        try:
            self._seed_body(hotel, opts)
        finally:
            post_save.connect(
                stock_signals._on_stock_movement_saved,
                sender=StockMovement,
            )
            post_save.connect(
                stock_signals._on_inventory_item_initial_lot,
                sender=InventoryItem,
            )

    def _seed_body(self, hotel, opts):
        today = timezone.localdate()
        rng = random.Random(7)
        compact = bool(opts.get("compact"))
        catalog = SEED_ITEMS[:8] if compact else SEED_ITEMS
        items = []
        for tpl in catalog:
            (
                name, category, wh, unit, qty, mn, mx, cost, sku, supplier, shelf, exp_days
            ) = tpl
            exp = today + timedelta(days=exp_days) if exp_days is not None else None
            is_restaurant = category == "Gıda dışı" and wh == "Mutfak"
            # Minibar adayları: küçük gramaj içecek / atıştırmalık kalemleri "HK" deposundaysa veya
            # adından mini bar formatı anlaşılıyorsa otomatik mini bar kataloğuna düşer.
            is_minibar = (
                wh in ("HK", "Bar")
                or any(s in name.lower() for s in ("330ml", "200ml", "375ml", "minibar", "fıstık", "kruvasan"))
            )
            usage = "stock_only"
            if is_restaurant:
                usage = "restaurant"
            elif is_minibar:
                usage = "minibar"
            sp = (
                (Decimal(str(cost)) * Decimal("1.75")).quantize(Decimal("0.01"))
                if usage in ("restaurant", "minibar")
                else None
            )
            it = InventoryItem.objects.create(
                hotel=hotel,
                name=name,
                category=category,
                warehouse=wh,
                unit=unit,
                quantity_on_hand=Decimal(str(qty)),
                min_quantity=Decimal(str(mn)),
                max_quantity=Decimal(str(mx)),
                unit_cost=Decimal(str(cost)),
                sku=sku,
                barcode=f"86012{rng.randint(10000, 99999)}{rng.randint(1, 9)}",
                supplier_name=supplier,
                location_in_warehouse=shelf,
                expiry_date=exp,
                last_restocked_at=timezone.now() - timedelta(days=rng.randint(1, 14)),
                notes="",
                is_archived=False,
                usage_area=usage,
                sale_price=sp,
            )
            items.append(it)

        for i, it in enumerate(items):
            base_qty = Decimal(str(rng.choice([20, 30, 40, 60, 100, 120, 200])))
            day_offset = rng.randint(7, 21)
            StockMovement.objects.create(
                hotel=hotel,
                item=it,
                movement_type="in",
                quantity=base_qty,
                unit_cost=it.unit_cost,
                to_warehouse=it.warehouse,
                reason="Tedarikçi teslimi",
                reference_no=f"PO-{1000 + i}",
                staff_name=rng.choice(["Ayşe", "Mehmet", "Selin", "Emre"]),
                business_date=today - timedelta(days=day_offset),
                note="",
            )
            n_out = 1 if compact else rng.randint(2, 5)
            for _ in range(n_out):
                out_qty = Decimal(str(rng.choice([2, 3, 5, 8, 10, 15])))
                d = today - timedelta(days=rng.randint(1, day_offset - 1))
                StockMovement.objects.create(
                    hotel=hotel,
                    item=it,
                    movement_type=rng.choice(["out", "out", "out", "waste"]),
                    quantity=out_qty,
                    unit_cost=it.unit_cost,
                    from_warehouse=it.warehouse,
                    reason=rng.choice(["Kat hizmetleri sarf", "Restoran sarf", "SPA sarf", "Kırık / bozuk"]),
                    staff_name=rng.choice(["Ayşe", "Mehmet", "Selin", "Emre", "Ali"]),
                    business_date=d,
                    note="",
                )

        if len(items) >= 4:
            src = items[0]
            half = (Decimal(src.quantity_on_hand) / Decimal(4)).quantize(Decimal("1"))
            StockMovement.objects.create(
                hotel=hotel,
                item=src,
                movement_type="transfer",
                quantity=half,
                unit_cost=src.unit_cost,
                from_warehouse=src.warehouse,
                to_warehouse="Mutfak",
                reason="Depolar arası transfer",
                staff_name="Selin",
                business_date=today - timedelta(days=2),
                note="Restoran sezonluk takviye",
            )

        sess = StockCountSession.objects.create(
            hotel=hotel,
            title="Ay sonu sayımı (örnek)",
            warehouse="Ana depo",
            started_on=today - timedelta(days=3),
            status="closed",
            closed_on=today - timedelta(days=2),
            note="Sayım kapatıldı; örnek veriler.",
        )
        for it in items[:6]:
            expected = it.quantity_on_hand
            counted = expected + Decimal(rng.choice([-3, -1, 0, 0, 0, 2, 4]))
            StockCountLine.objects.create(
                session=sess,
                item=it,
                expected_qty=expected,
                counted_qty=max(Decimal("0"), counted),
                note="" if counted == expected else "Fark fiziksel doğrulandı",
            )

        for it in InventoryItem.objects.filter(hotel=hotel):
            q = it.quantity_on_hand
            if q is None or q <= 0:
                continue
            if InventoryStockLot.objects.filter(item=it).exists():
                continue
            InventoryStockLot.objects.create(
                hotel=hotel,
                item=it,
                quantity_initial=q,
                quantity_remaining=q,
                unit_cost=it.unit_cost,
                expiry_date=it.expiry_date,
                note="Demo (tek sentez parti)",
            )

        self.stdout.write(self.style.SUCCESS(
            f"Stok demo verisi yüklendi: {len(items)} ürün · "
            f"{StockMovement.objects.filter(hotel=hotel).count()} hareket · "
            f"{StockCountSession.objects.filter(hotel=hotel).count()} sayım."
        ))
