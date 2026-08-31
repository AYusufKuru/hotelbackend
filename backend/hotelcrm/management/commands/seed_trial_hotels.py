"""25 inceleme oteli: benzersiz isim, kullanıcı ve şifre.

Kullanıcı süperuser değildir; şube listesinde yalnızca kendi otelini görür.

  py manage.py seed_trial_hotels
  py manage.py seed_trial_hotels --skip-data
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hotelcrm.models import Hotel, Permission, Role, RolePermission, UserRole

User = get_user_model()

# (kod, otel adı, şehir, sokak, ilçe, lat, lng, kullanıcı, şifre)
TRIAL_ACCOUNTS: tuple[tuple, ...] = (
    ("HT01", "Hoterfea Pera Konak", "İstanbul", "Muallim Naci Cad.", "Beşiktaş", Decimal("41.047350"), Decimal("29.026880"), "pera.yonetim", "Pera#Kule92"),
    ("HT02", "Hoterfea Lara Beach", "Antalya", "Lara Turizm Yolu", "Muratpaşa", Decimal("36.856210"), Decimal("30.837440"), "lara.mudur", "Lara!Sahil47"),
    ("HT03", "Hoterfea Bodrum Yalı", "Muğla", "Yalı Caddesi", "Bodrum", Decimal("37.034400"), Decimal("27.430500"), "bodrum.otel", "Yali&Deniz63"),
    ("HT04", "Hoterfea Kuşadası Marina", "Aydın", "Kuşadası Sahil", "Kuşadası", Decimal("37.857900"), Decimal("27.259700"), "marina.kaptan", "Marina^Gunes28"),
    ("HT05", "Hoterfea Göreme Cave", "Nevşehir", "Müze Cad.", "Göreme", Decimal("38.643100"), Decimal("34.828900"), "goreme.cave", "Cave*Peri15"),
    ("HT06", "Hoterfea Alaçatı Rüzgar", "İzmir", "Kemalpaşa Cad.", "Çeşme", Decimal("38.322700"), Decimal("26.374200"), "alacati.ruzgar", "Ruzgar~Meltem81"),
    ("HT07", "Hoterfea Cunda Liman", "Balıkesir", "Ayvalık Iskele", "Ayvalık", Decimal("39.316700"), Decimal("26.695600"), "cunda.liman", "Cunda$Zeytin54"),
    ("HT08", "Hoterfea Uludağ Kar", "Bursa", "Oteller Bölgesi", "Osmangazi", Decimal("40.098200"), Decimal("29.131100"), "uludag.kar", "Uludag%Kar36"),
    ("HT09", "Hoterfea Sümela Yayla", "Trabzon", "Maçka Yolu", "Maçka", Decimal("40.688900"), Decimal("39.658100"), "sumela.yayla", "Sumela+Yayla72"),
    ("HT10", "Hoterfea Antep Bey", "Gaziantep", "İncilipınar", "Şehitkamil", Decimal("37.066200"), Decimal("37.383300"), "antep.bey", "Antep!Fistik44"),
    ("HT11", "Hoterfea Van Gölü", "Van", "İskele Cad.", "İpekyolu", Decimal("38.489100"), Decimal("43.408900"), "van.gol", "VanGol#Inci19"),
    ("HT12", "Hoterfea Mardin Taş", "Mardin", "1. Cadde", "Artuklu", Decimal("37.312900"), Decimal("40.733900"), "mardin.tas", "Mardin*Tas88"),
    ("HT13", "Hoterfea Rize Çay", "Rize", "Sahil Yolu", "Merkez", Decimal("41.020100"), Decimal("40.523400"), "rize.cay", "RizeCay&Yesil23"),
    ("HT14", "Hoterfea Pamukkale Termal", "Denizli", "Pamukkale Yolu", "Pamukkale", Decimal("37.920000"), Decimal("29.121000"), "pamukkale.termal", "Termal^Traverten61"),
    ("HT15", "Hoterfea Göcek Marin", "Muğla", "Göcek İskele", "Fethiye", Decimal("36.753200"), Decimal("28.943100"), "gocek.marin", "Gocek~Tekne07"),
    ("HT16", "Hoterfea Side Antik", "Antalya", "Side Antik Cad.", "Manavgat", Decimal("36.766700"), Decimal("31.388900"), "side.antik", "SideAntik$Apollon35"),
    ("HT17", "Hoterfea Assos Kuzey", "Çanakkale", "Behramkale", "Ayvacık", Decimal("39.490600"), Decimal("26.336900"), "assos.kuzey", "AssosKuzey+Athena52"),
    ("HT18", "Hoterfea Bozcaada Bağ", "Çanakkale", "Cumhuriyet Mah.", "Bozcaada", Decimal("39.835000"), Decimal("26.069700"), "bozcaada.bag", "Bozcaada!Bag77"),
    ("HT19", "Hoterfea Sapanca Göl", "Sakarya", "Kırkpınar", "Sapanca", Decimal("40.691100"), Decimal("30.267500"), "sapanca.gol", "Sapanca#Gol14"),
    ("HT20", "Hoterfea Abant Orman", "Bolu", "Abant Gölü", "Mudurnu", Decimal("40.605600"), Decimal("31.277800"), "abant.orman", "AbantOrman*Ced29"),
    ("HT21", "Hoterfea Ölüdeniz", "Muğla", "Belcekız", "Fethiye", Decimal("36.551100"), Decimal("29.121400"), "oludeniz.belcekiz", "Oludeniz&Mavi68"),
    ("HT22", "Hoterfea Kaş Meis", "Antalya", "Hastane Cad.", "Kaş", Decimal("36.201900"), Decimal("29.637800"), "kas.meis", "KasMeis^Likya41"),
    ("HT23", "Hoterfea Datça Ege", "Muğla", "İskele Mah.", "Datça", Decimal("36.727800"), Decimal("27.686700"), "datca.ege", "DatcaEge~Badem16"),
    ("HT24", "Hoterfea Amasra Kale", "Bartın", "Kum Mah.", "Amasra", Decimal("41.749400"), Decimal("32.386400"), "amasra.kale", "AmasraKale$Tarih83"),
    ("HT25", "Hoterfea Safranbolu Konak", "Karabük", "Çeşme Mah.", "Safranbolu", Decimal("41.250800"), Decimal("32.694200"), "safranbolu.konak", "Safran!Konak57"),
)

CREDENTIALS_FILE = Path(__file__).resolve().parents[4] / "inceleme-girisleri.txt"


def _owner_role() -> Role:
    role, _ = Role.objects.get_or_create(
        code="owner",
        defaults={"name": "İşletme sahibi / patron"},
    )
    perm, _ = Permission.objects.get_or_create(
        code="mod.all",
        defaults={"description": "Otelde açık olan tüm modüllere erişim"},
    )
    RolePermission.objects.get_or_create(role=role, permission=perm)
    for extra in ("users.manage", "tasks.assign"):
        p, _ = Permission.objects.get_or_create(code=extra, defaults={"description": extra})
        RolePermission.objects.get_or_create(role=role, permission=p)
    return role


def _find_user(hotel: Hotel, new_username: str, index: int) -> tuple:
    user = User.objects.filter(username=new_username).first()
    if user:
        return user, False
    old = User.objects.filter(username=f"inceleme{index}").first()
    if old:
        return old, False
    linked = (
        UserRole.objects.filter(hotel=hotel, user__is_superuser=False)
        .select_related("user")
        .first()
    )
    if linked:
        return linked.user, False
    return None, True


class Command(BaseCommand):
    help = "25 inceleme oteli: benzersiz ad, kullanıcı, şifre ve demo veri."

    def add_arguments(self, parser):
        parser.add_argument("--skip-data", action="store_true")

    def handle(self, *args, **options):
        role = _owner_role()
        skip_data = bool(options["skip_data"])
        lines = [
            "HOTERFEA INCELEME GIRIS BILGILERI",
            "Bu dosyayi baskasiyla paylasma. Her otel yalniz kendi hesabini kullanir.",
            "Kapatmak icin ilgili kullaniciyi pasif et (is_active=False).",
            "",
        ]

        for i, spec in enumerate(TRIAL_ACCOUNTS, start=1):
            code, name, city, street, district, lat, lng, uname, password = spec
            with transaction.atomic():
                hotel, created = Hotel.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "city": city,
                        "property_type": "hotel",
                        "capacity_rooms": 48 + (i % 20) * 2,
                        "address": f"{street} No:{10 + i}, {district} / {city}",
                        "latitude": lat,
                        "longitude": lng,
                        "tax_id": f"{1000000000 + i:010d}"[:10],
                        "trade_title": f"{name} Turizm A.Ş.",
                        "board_rate_bb": Decimal("0"),
                        "board_rate_hb": Decimal("280") + i,
                        "board_rate_fb": Decimal("480") + i,
                        "board_rate_ai": Decimal("690") + i,
                    },
                )
                user, is_new = _find_user(hotel, uname, i)
                if user is None:
                    user = User(username=uname)
                    is_new = True
                taken = User.objects.filter(username=uname).exclude(pk=user.pk).exists() if user.pk else User.objects.filter(username=uname).exists()
                if taken:
                    raise CommandError(f"Kullanici adi dolu: {uname}")
                user.username = uname
                user.email = f"{uname}@hoterfea-demo.test"
                user.is_staff = False
                user.is_superuser = False
                user.is_active = True
                user.set_password(password)
                user.save()
                UserRole.objects.update_or_create(
                    user=user, hotel=hotel, defaults={"role": role}
                )
                UserRole.objects.filter(user=user).exclude(hotel=hotel).delete()

            flag = "yeni" if created else "guncel"
            self.stdout.write(f"{code} {name} ({flag}) user={uname}")
            lines.extend(
                [
                    f"--- {name} ---",
                    f"Otel kodu : {code}",
                    f"Sehir     : {city}",
                    f"Kullanici : {uname}",
                    f"Sifre     : {password}",
                    "",
                ]
            )

            if skip_data:
                continue
            call_command("seed_pms_test_data", hotel=code, wipe=True, compact=True)
            call_command("seed_accounting_test_data", hotel=code, wipe=True)
            call_command("seed_stock_demo", hotel=code, wipe=True)
            call_command("seed_ops_demo", hotel=code, wipe=True)

        try:
            CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            CREDENTIALS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Giris listesi: {CREDENTIALS_FILE}"))
        except OSError as exc:
            self.stdout.write(f"txt yazilamadi (yayinda normal olabilir): {exc}")
