from django.core.management.base import BaseCommand

from hotelcrm.models import Hotel


class Command(BaseCommand):
    help = "Örnek bir otel kaydı oluşturur (kod DEMO yoksa)."

    def handle(self, *args, **options):
        h, created = Hotel.objects.get_or_create(
            code="DEMO",
            defaults={
                "name": "Demo Otel",
                "city": "İstanbul",
                "property_type": "hotel",
                "capacity_rooms": 50,
            },
        )
        action = "oluşturuldu" if created else "zaten vardı"
        self.stdout.write(self.style.SUCCESS(f"{action}: {h.code} — {h.name} (id={h.pk})"))
