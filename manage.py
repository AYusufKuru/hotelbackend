#!/usr/bin/env python
"""
Vercel ve Git repo kökü: Django uygulaması `backend/` altında.
Bu dosya kökte olduğu için framework tespiti ve `vc deploy` çalışır.
Lokal: `python manage.py` (buradan) veya `cd backend && python manage.py` aynı projeyi kullanır.
"""
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
_backend = _root / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    from dotenv import load_dotenv

    load_dotenv(_backend / ".env")
    load_dotenv(_backend / ".env.local", override=True)
except ImportError:
    pass


def main() -> None:
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
