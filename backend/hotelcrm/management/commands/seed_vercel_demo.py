"""
Vercel (veya baska CI) build/deploy: DEMO otel + PMS + muhasebe demo verisi.

Her calistirmada once --wipe ile isaretli tohum kayitlari silinir, sonra yeniden uretilir;
ard arda build alinsa bile cift kayit birikmez.

Ortam: SEED_DEMO_ON_DEPLOY=1 (veya true/yes/on). Acik degilse komut hicbir sey yapmaz (cikis 0).

PMS: varsayilan olarak seed_pms_test_data --compact (Vercel build suresi kisa).
Tam agir yuk: SEED_DEMO_FULL=1 (dakikalar surebilir; zaman asimi riski).

(PMS komutu bitince otomatik olarak İK demo personeli de yüklenir: `seed_hr_test_data`.)

Sira: seed_demo_hotel -> seed_pms_test_data --wipe [--compact] -> seed_accounting_test_data --wipe
"""

from __future__ import annotations

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


class Command(BaseCommand):
    help = (
        "Vercel deploy demo verisi: SEED_DEMO_ON_DEPLOY=1 iken DEMO otel, PMS ve muhasebe "
        "tohumunu once siler sonra yukler."
    )

    def handle(self, *args, **options):
        if not _truthy("SEED_DEMO_ON_DEPLOY"):
            self.stdout.write(
                "seed_vercel_demo: skipped (set SEED_DEMO_ON_DEPLOY=1 on Vercel to load demo data)."
            )
            return

        hotel = "DEMO"
        pms_compact = not _truthy("SEED_DEMO_FULL")
        if pms_compact:
            self.stdout.write(
                "seed_vercel_demo: using compact PMS seed (fast build). "
                "Set SEED_DEMO_FULL=1 for full dataset (slow; may timeout on Vercel)."
            )
        else:
            self.stdout.write(
                "seed_vercel_demo: full PMS seed (SEED_DEMO_FULL=1) — this may take several minutes."
            )

        self.stdout.write("seed_vercel_demo: ensuring DEMO hotel...")
        call_command("seed_demo_hotel")

        self.stdout.write("seed_vercel_demo: PMS seed (wipe then load)...")
        call_command("seed_pms_test_data", hotel=hotel, wipe=True, compact=pms_compact)

        self.stdout.write("seed_vercel_demo: accounting seed (wipe then load)...")
        call_command("seed_accounting_test_data", hotel=hotel, wipe=True)

        self.stdout.write("seed_vercel_demo: stock seed (wipe then load)...")
        call_command("seed_stock_demo", hotel=hotel, wipe=True)

        self.stdout.write(self.style.SUCCESS("seed_vercel_demo: done."))
