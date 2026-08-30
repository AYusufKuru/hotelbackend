from decimal import Decimal

from django.core.management.base import BaseCommand

from hotelcrm.models import Hotel

HOTELS = (
    {
        "code": "DEMO",
        "name": "hoterfea demo otel 1",
        "city": "İstanbul",
        "property_type": "hotel",
        "capacity_rooms": 86,
        "address": "Muallim Naci Cad. No:18, Ortaköy, Beşiktaş / İstanbul",
        "latitude": Decimal("41.047350"),
        "longitude": Decimal("29.026880"),
        "tax_id": "1234567890",
        "trade_title": "Hoterfea Demo Otel 1 Turizm A.Ş.",
        "board_rate_bb": Decimal("0"),
        "board_rate_hb": Decimal("350"),
        "board_rate_fb": Decimal("550"),
        "board_rate_ai": Decimal("750"),
    },
    {
        "code": "DEMO2",
        "aliases": ("GRD-01", "GRD01"),
        "name": "hoterfea demo otel 2",
        "city": "Antalya",
        "property_type": "hotel",
        "capacity_rooms": 64,
        "address": "Lara Turizm Yolu No:12, Muratpaşa / Antalya",
        "latitude": Decimal("36.856210"),
        "longitude": Decimal("30.837440"),
        "tax_id": "9876543210",
        "trade_title": "Hoterfea Demo Otel 2 Turizm A.Ş.",
        "board_rate_bb": Decimal("0"),
        "board_rate_hb": Decimal("280"),
        "board_rate_fb": Decimal("480"),
        "board_rate_ai": Decimal("690"),
    },
)


def upsert_demo_hotels() -> list[Hotel]:
    out: list[Hotel] = []
    for spec in HOTELS:
        aliases = spec.get("aliases") or ()
        fields = {k: v for k, v in spec.items() if k not in ("aliases",)}
        hotel = Hotel.objects.filter(code=fields["code"]).first()
        if hotel is None:
            for alias in aliases:
                hotel = Hotel.objects.filter(code=alias).first()
                if hotel:
                    hotel.code = fields["code"]
                    break
        if hotel is None:
            hotel = Hotel.objects.create(**fields)
        else:
            for key, value in fields.items():
                setattr(hotel, key, value)
            hotel.save()
        out.append(hotel)
    return out


class Command(BaseCommand):
    help = "Sunum otellerini oluşturur / isimlerini günceller (hoterfea demo otel 1 ve 2)."

    def handle(self, *args, **options):
        for h in upsert_demo_hotels():
            self.stdout.write(self.style.SUCCESS(f"{h.code} — {h.name} (id={h.pk})"))
