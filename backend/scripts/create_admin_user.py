"""admin kullanıcı yoksa oluşturur.

  cd backend
  .\\.venv\\Scripts\\python.exe scripts\\create_admin_user.py

İsteğe bağlı: $env:HOTELCRM_ADMIN_PASSWORD = '...'
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
USERNAME = "admin"
EMAIL = "admin@local"
PASSWORD = os.environ.get("HOTELCRM_ADMIN_PASSWORD", "Admin1234!")

if User.objects.filter(username=USERNAME).exists():
    print(f"Kullanıcı zaten var: {USERNAME}")
else:
    User.objects.create_superuser(USERNAME, EMAIL, PASSWORD)
    print(f"Oluşturuldu: {USERNAME}")
    print("Şifre ortam değişkeni HOTELCRM_ADMIN_PASSWORD ile de verilebilir (varsayılan geliştirme şifresi).")
