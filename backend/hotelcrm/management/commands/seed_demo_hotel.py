from decimal import Decimal

from django.core.management.base import BaseCommand

from hotelcrm.models import Hotel


class Command(BaseCommand):
    help = "DEMO otel kaydını oluşturur veya sunum için profilini günceller."

    def handle(self, *args, **options):
        defaults = {
            "name": "Demo Grand Hotel İstanbul",
            "city": "İstanbul",
            "property_type": "hotel",
            "capacity_rooms": 86,
            "address": "Muallim Naci Cad. No:18, Ortaköy, Beşiktaş / İstanbul",
            "latitude": Decimal("41.047350"),
            "longitude": Decimal("29.026880"),
            "tax_id": "1234567890",
            "trade_title": "Demo Grand Hotel Turizm İşletmeleri A.Ş.",
            "board_rate_bb": Decimal("0"),
            "board_rate_hb": Decimal("350"),
            "board_rate_fb": Decimal("550"),
            "board_rate_ai": Decimal("750"),
        }
        h, created = Hotel.objects.get_or_create(code="DEMO", defaults=defaults)
        if not created:
            for key, value in defaults.items():
                setattr(h, key, value)
            h.save()
        action = "oluşturuldu" if created else "güncellendi"
        self.stdout.write(self.style.SUCCESS(f"{action}: {h.code} — {h.name} (id={h.pk})"))
