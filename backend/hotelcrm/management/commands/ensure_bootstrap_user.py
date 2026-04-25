import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Vercel / ilk kurulum: ortam değişkenlerinden tek bir süper kullanıcı oluşturur. "
        "Kullanıcı zaten varsa yalnız yetkileri günceller, şifreyi SADECE "
        "DJANGO_SUPERUSER_RESET_PASSWORD=1 iken değiştirir (repoda şifre yoktur)."
    )

    def handle(self, *args, **options):
        flag = (os.environ.get("DJANGO_BOOTSTRAP_SUPERUSER") or "").strip().lower()
        if flag not in ("1", "true", "yes", "on"):
            self.stdout.write("ensure_bootstrap_user: atlandı (DJANGO_BOOTSTRAP_SUPERUSER açık değil).")
            return

        username = (os.environ.get("DJANGO_SUPERUSER_USERNAME") or "admin").strip() or "admin"
        password = (os.environ.get("DJANGO_SUPERUSER_PASSWORD") or "").strip()
        if not password:
            self.stderr.write(
                self.style.ERROR("DJANGO_BOOTSTRAP_SUPERUSER açık ama DJANGO_SUPERUSER_PASSWORD boş; iptal.")
            )
            return

        email = (os.environ.get("DJANGO_SUPERUSER_EMAIL") or f"{username}@localhost").strip()
        reset_pwd = (os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        u, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        u.is_staff = True
        u.is_superuser = True
        u.is_active = True
        if not u.email:
            u.email = email

        if created or reset_pwd:
            u.set_password(password)
            u.save()
            if created:
                self.stdout.write(self.style.SUCCESS(f"Süper kullanıcı oluşturuldu: {username!r}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Şifre güncellendi: {username!r} (DJANGO_SUPERUSER_RESET_PASSWORD)"))
        else:
            u.save()
            self.stdout.write(
                self.style.WARNING(
                    f"Kullanıcı zaten vardı, şifre değişmedi: {username!r}. "
                    "Bir kez DJANGO_SUPERUSER_RESET_PASSWORD=1 verip deploy et veya admin’den değiştir."
                )
            )
