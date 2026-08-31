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
        on_vercel = (os.environ.get("VERCEL") or "").strip() == "1"
        skip = (os.environ.get("SEED_DEMO_ON_DEPLOY") or "").strip().lower() in ("0", "false", "no", "off")
        if skip:
            self.stdout.write("seed_vercel_demo: skipped (SEED_DEMO_ON_DEPLOY=0).")
            return
        if not on_vercel and not _truthy("SEED_DEMO_ON_DEPLOY"):
            self.stdout.write(
                "seed_vercel_demo: skipped (yerelde SEED_DEMO_ON_DEPLOY=1 verin; Vercel'de otomatik çalışır)."
            )
            return

        try:
            self.stdout.write("seed_vercel_demo: 25 inceleme oteli + üyelik + veri...")
            call_command("seed_trial_hotels", count=25)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"seed_vercel_demo başarısız (yayın devam eder): {exc}"))
            return

        self.stdout.write(self.style.SUCCESS("seed_vercel_demo: done."))
