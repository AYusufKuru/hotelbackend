"""Vercel build adımları — hangisinin düştüğü logda net görünsün.

migrate zorunlu. Superuser / demo seed hatası yayını kırmaz.
collectstatic Vercel Django builder tarafından ayrıca çalıştırılır.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _run(label: str, args: list[str], *, required: bool) -> None:
    print(f"\n===== {label} =====", flush=True)
    proc = subprocess.run([sys.executable, "manage.py", *args], check=False)
    if proc.returncode == 0:
        print(f"OK: {label}", flush=True)
        return
    print(f"HATA: {label} çıkış kodu {proc.returncode}", flush=True)
    if required:
        sys.exit(proc.returncode)
    print(f"UYARI: {label} atlandı; deploy devam ediyor.", flush=True)


def main() -> None:
    db = (os.environ.get("DATABASE_URL") or "").strip()
    pwd = (os.environ.get("DJANGO_SUPERUSER_PASSWORD") or "").strip()
    print(f"DATABASE_URL tanımlı: {bool(db)}", flush=True)
    print(f"VERCEL={os.environ.get('VERCEL')!r}", flush=True)
    print(f"DJANGO_BOOTSTRAP_SUPERUSER={os.environ.get('DJANGO_BOOTSTRAP_SUPERUSER')!r}", flush=True)
    print(f"DJANGO_SUPERUSER_PASSWORD tanımlı: {bool(pwd)}", flush=True)
    print(f"SEED_DEMO_ON_DEPLOY={os.environ.get('SEED_DEMO_ON_DEPLOY')!r}", flush=True)

    if not db:
        print(
            "HATA: Build ortamında DATABASE_URL yok. Vercel → Settings → Environment "
            "Variables içinde DATABASE_URL'i Production + Preview için ekleyin "
            "(Build sırasında da erişilebilir olmalı).",
            flush=True,
        )
        sys.exit(1)

    _run("migrate", ["migrate", "--noinput"], required=True)
    _run("ensure_bootstrap_user", ["ensure_bootstrap_user"], required=False)
    _run("seed_vercel_demo", ["seed_vercel_demo"], required=False)


if __name__ == "__main__":
    main()
