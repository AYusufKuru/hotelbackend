"""
Otel içindeki veriyi siler (otel kaydının kendisi kalır).

Kullanım:
  py manage.py wipe_hotel_data --hotel=MAV --dry-run
  py manage.py wipe_hotel_data --hotel=MAV --confirm
  py manage.py wipe_hotel_data --hotel=MAV --scope=reservations --confirm
  py manage.py wipe_hotel_data --hotel=MAV --scope=reservations,guests --confirm

Scope değerleri:
  reservations  — rezervasyon, folio, ödeme, KBS
  operations    — kasa, görev, F&B, SPA, minibar, çamaşır, entegrasyon vb.
  inventory     — stok kalemleri, lot, hareket, sayım
  accounting    — GL, fatura, yevmiye, cari, demirbaş, acente
  staff         — personel, departman, işe alım
  guests        — misafir kartları
  rooms         — oda, oda tipi, kanal
  all           — hepsi (varsayılan)
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from hotelcrm.hotel_data_purge import ALL_SCOPES, purge_hotel_data
from hotelcrm.models import Hotel


class Command(BaseCommand):
    help = "Otel kaydını silmeden otel kapsamındaki veriyi temizler."

    def add_arguments(self, parser):
        parser.add_argument("--hotel", required=True, help="Otel code (Hotel.code), örn. MAV")
        parser.add_argument(
            "--scope",
            default="all",
            help="Virgülle ayrılmış kapsam: reservations,operations,inventory,accounting,staff,guests,rooms,all",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Silmeden kaç kayıt etkileneceğini göster.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Gerçekten sil (yoksa sadece dry-run yapılır).",
        )
        parser.add_argument(
            "--no-reset-sequences",
            action="store_true",
            help="Misafir/rezervasyon kod sayaçlarını sıfırlama.",
        )

    def handle(self, *args, **options):
        code = str(options["hotel"]).strip()
        hotel = Hotel.objects.filter(code__iexact=code).first()
        if not hotel:
            raise CommandError(f"Otel bulunamadı: code={code!r}")

        scopes = [s.strip() for s in str(options["scope"]).split(",") if s.strip()]
        unknown = set(scopes) - ALL_SCOPES
        if unknown:
            raise CommandError(f"Bilinmeyen scope: {', '.join(sorted(unknown))}")

        dry_run = bool(options["dry_run"]) or not options["confirm"]
        if not options["dry_run"] and not options["confirm"]:
            self.stdout.write(
                self.style.WARNING(
                    "Güvenlik: --confirm verilmedi, dry-run modunda çalışılıyor. "
                    "Silmek için --confirm ekleyin.",
                ),
            )

        result = purge_hotel_data(
            hotel,
            scopes=scopes,
            dry_run=dry_run,
            reset_sequences=not options["no_reset_sequences"],
        )

        mode = "DRY-RUN" if dry_run else "SİLİNDİ"
        self.stdout.write(self.style.SUCCESS(f"{mode}: {hotel.code} ({hotel.name})"))
        self.stdout.write(f"Scope: {', '.join(result.scopes)}")
        for key, count in sorted(result.deleted.items()):
            if count:
                self.stdout.write(f"  {key}: {count}")
        self.stdout.write(f"Toplam etkilenen kayıt: {result.total}")
