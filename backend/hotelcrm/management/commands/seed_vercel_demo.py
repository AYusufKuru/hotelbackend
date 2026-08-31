"""Vercel deploy: 25 inceleme oteli + kullanici + demo veri.

count=25 GECERSIZDIR (seed_trial_hotels --count kabul etmez); o hata
yayinda sessizce yutuluyordu, bu yuzden sadece admin kaliyordu.

Once kullanicilar (--skip-data), sonra demo veri. Veri adimi duserse
kullanicilar yine de kalir. Sonraki deploy'larda wipe yapilmaz
(SEED_DEMO_FORCE=1 ile zorla yeniden tohumlanir).
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

User = get_user_model()


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


class Command(BaseCommand):
    help = "Vercel: 25 inceleme oteli, kullanici ve demo veri."

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

        already = User.objects.filter(username="pera.yonetim").exists()
        force = _truthy("SEED_DEMO_FORCE")

        try:
            self.stdout.write("seed_vercel_demo: 25 otel + kullanici...")
            call_command("seed_trial_hotels", skip_data=True)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"seed_vercel_demo kullanicilar basarisiz: {exc}"))
            raise

        if already and not force:
            self.stdout.write(
                "seed_vercel_demo: kullanicilar zaten vardi; demo veri wipe atlandi "
                "(yeniden tohum icin SEED_DEMO_FORCE=1)."
            )
            self.stdout.write(self.style.SUCCESS("seed_vercel_demo: done."))
            return

        try:
            self.stdout.write("seed_vercel_demo: demo veri (PMS/muhasebe/stok/ops)...")
            call_command("seed_trial_hotels")
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"seed_vercel_demo veri adimi basarisiz (kullanicilar yuklu kalir): {exc}"
                )
            )

        self.stdout.write(self.style.SUCCESS("seed_vercel_demo: done."))
