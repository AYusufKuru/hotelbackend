"""Asistan için salt okunur otel özeti — veritabanından JSON blok."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Any

from django.db.models import Prefetch
from django.utils import timezone

from hotelcrm.models import Hotel, OperationalTask, Reservation, ReservationOccupant, Room
from hotelcrm.models.enums import (
    ReservationStatus,
    RoomOccupancyStatus,
    TaskStatus,
)


def _guest_line(g: Any) -> str:
    fn = getattr(g, "first_name", "") or ""
    ln = getattr(g, "last_name", "") or ""
    n = (f"{fn} {ln}").strip()
    return n or (getattr(g, "display_code", None) or str(getattr(g, "pk", ""))[:8])


def normalize_hotel_id(raw: Any) -> uuid.UUID | None:
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return None


def resolve_hotel_id(raw: Any) -> uuid.UUID | None:
    """İstekteki hotel_id; yoksa yalnız tek otel kayıtlıysa onun id'si."""
    hid = normalize_hotel_id(raw)
    if hid:
        return hid if Hotel.objects.filter(pk=hid).exists() else None
    if Hotel.objects.count() == 1:
        row = Hotel.objects.only("id").first()
        return row.pk if row else None
    return None


def _normalize_question(s: str) -> str:
    t = s.casefold().strip()
    for a, b in (
        ("ı", "i"),
        ("ğ", "g"),
        ("ü", "u"),
        ("ş", "s"),
        ("ö", "o"),
        ("ç", "c"),
    ):
        t = t.replace(a, b)
    return t


def is_inside_guest_count_question(user_text: str) -> bool:
    """
    'İçeride / otelde kaç kişi' vb. — isim sorma niyetini hariç tut.
    """
    n = _normalize_question(user_text)
    if not n:
        return False
    if "isim" in n and any(x in n for x in ("ne", "kim", "liste", "tam", "hepsi")):
        return False
    needles = (
        "kac kisi",
        "kac misafir",
        "kac insan",
        "otelde kac",
        "oteldeki kac",
        "iceride kac",
        "icerde kac",
        "içeride kac",
        "içerde kac",
        "iceride kim",
        "otelde kisi",
        "otelde kac kisi",
    )
    return any(x in n for x in needles)


def is_guest_names_question(user_text: str) -> bool:
    """Konaklayan adları kim / isimleri ne — sayı sorusundan ayrılır."""
    n = _normalize_question(user_text)
    if not n or is_inside_guest_count_question(user_text):
        return False
    if "isimleri" in n:
        return True
    if "isim" in n and any(x in n for x in ("ne", "kim", "liste")):
        return True
    if "konaklayan" in n and "kim" in n:
        return True
    return False


def is_navigate_new_reservation(user_text: str) -> bool:
    """Yeni rezervasyon sihirbazı / ekleme ekranına gitme niyeti."""
    n = _normalize_question(user_text)
    if not n:
        return False
    needles = (
        "yeni rezervasyon",
        "yeni kayit",
        "rezervasyon sihirbaz",
        "rezervasyon ekle",
        "rezervasyon ac",
        "rezervasyon olustur",
        "rezervasyon kaydi",
        "rezervasyon kaydet",
        "rezervasyon formu",
        "rezervasyon sayfas",
        "rezervasyon ekran",
        "rezervasyon yap",
        "rezervasyon ekleme",
        "rezervasyon acmak",
        "oda ayirt",
        "bana rezervasyon",
        "rezervasyon sayfasina",
        "rezervasyon ekranina",
    )
    if any(x in n for x in needles):
        return True
    # Tek kelime — sık "rezervasyon" yazılıyor; yeni rezervasyon ekranına yönlendir
    core = n.strip("?!.,").strip()
    if core == "rezervasyon":
        return True
    return False


def looks_like_volunteered_inhouse_count_reply(user_text: str, assistant_reply: str) -> bool:
    """
    Kullanıcı içeride / otelde kaç kişi sormadığı halde modelin doluluk özeti dökmesi.
    """
    if is_inside_guest_count_question(user_text):
        return False
    if not (assistant_reply or "").strip():
        return False
    q = _normalize_question(assistant_reply)
    q_loose = q.replace("*", "").replace("_", "").replace("`", "")
    markers = (
        "otelde kac kisi",
        "otelde kac misafir",
        "otelde kisi var",
        "iceride:",
        "iceride kac",
        "sidebar_iceride",
        "iceride_gosterilen",
    )
    if any(m in q for m in markers):
        return True
    if "iceride:" in q_loose:
        return True
    # "**1**" + tekrar kalıbı (model tekrarlayan özet üretince)
    if "tekrar" in q and "kac" in q and ("otelde" in q or "iceride" in q):
        return True
    return False


def reply_guest_names_from_digest(digest: dict[str, Any]) -> str:
    blok = digest["konaklamada_check_in_rezervasyonlari"]
    isimler: list[str] = list(blok["benzersiz_isim_satirlari"])
    ana_satirlar: list[str] = []
    for d in blok["detaylar"]:
        a = (d.get("ana_misafir_alanda_yazan") or "").strip()
        if a and a not in isimler:
            ana_satirlar.append(a)
    if isimler:
        core = ", ".join(isimler)
        if ana_satirlar:
            return f"Misafir: {core}. Ek satır: {', '.join(ana_satirlar)}."
        return f"Misafir: {core}."
    if ana_satirlar:
        return f"Misafir (rezervasyon ana satırı): {', '.join(ana_satirlar)}."
    return "Aktif check-in özette görünür ad yok."


def build_hotel_digest(hotel_pk: uuid.UUID) -> dict[str, Any]:
    """Otel özeti (dict). Otel yoksa ValueError."""
    hotel = Hotel.objects.filter(pk=hotel_pk).only("code", "name", "city").first()
    if not hotel:
        raise ValueError("otel bulunamadı")

    today = timezone.localdate()
    week_ahead = today + timedelta(days=7)

    rooms_q = Room.objects.filter(hotel_id=hotel_pk)
    rooms_total = rooms_q.count()
    rooms_occupied = rooms_q.filter(
        occupancy_status=RoomOccupancyStatus.OCCUPIED,
    ).count()

    rez_base = Reservation.objects.filter(hotel_id=hotel_pk)

    # Masaüstü stats.inHouse ile aynı: status=checked_in (tarih filtresi yok)
    checked_in_qs = rez_base.filter(status=ReservationStatus.CHECKED_IN)
    iceride_rezervasyon_sayisi = checked_in_qs.count()
    toplam_yetiskin_alani = sum(int(r.adults or 1) for r in checked_in_qs.only("adults"))

    prefetch_occ = Prefetch(
        "occupants",
        queryset=ReservationOccupant.objects.select_related("guest").order_by(
            "sequence",
            "id",
        ),
    )

    konaklamada_qs = (
        checked_in_qs.select_related("room", "guest")
        .prefetch_related(prefetch_occ)
        .order_by("check_out_date", "display_code")
    )

    def rez_line(r: Reservation) -> dict[str, Any]:
        occ_qs = list(r.occupants.all())
        if occ_qs:
            names = [_guest_line(o.guest) for o in occ_qs]
        else:
            pname = (r.primary_guest_name or "").strip()
            names = [pname] if pname else []
        return {
            "rezervasyon_kodu": r.display_code or str(r.pk)[:8],
            "ana_misafir_alanda_yazan": r.primary_guest_name or "",
            "oda_no": getattr(r.room, "room_number", "") if r.room_id else "",
            "giris": str(r.check_in_date),
            "cikis": str(r.check_out_date),
            "konaklamada_isimler": names,
            "yetiskin_sayi_alani": int(r.adults or 1),
            "bakiye_tl": float(r.balance_amount or 0),
        }

    konaklamalar = [rez_line(r) for r in konaklamada_qs]

    all_names_flat: list[str] = []
    for k in konaklamalar:
        all_names_flat.extend(k["konaklamada_isimler"])

    unique_person_labels = sorted({n.strip() for n in all_names_flat if n.strip()})

    bugun_giris_bekleyen_qs = rez_base.filter(
        status=ReservationStatus.UPCOMING,
        check_in_date=today,
    ).order_by("created_at")[:50]

    bugun_giris = [
        {
            "kod": x.display_code or str(x.pk)[:8],
            "misafir_alanda_yazan": x.primary_guest_name or "",
            "oda_atandi": getattr(x.room, "room_number", "") if x.room_id else "",
        }
        for x in bugun_giris_bekleyen_qs
    ]

    pending_tasks_qs = (
        OperationalTask.objects.filter(hotel_id=hotel_pk)
        .exclude(status=TaskStatus.DONE)
        .only("display_code", "title", "status", "priority", "category", "pk")
        .order_by("-created_at")[:20]
    )
    bekleyen_gorevler = [
        {
            "kod": t.display_code or str(t.pk)[:8],
            "baslik": (t.title or "")[:200],
            "durum": t.status,
            "oncelik": t.priority or "",
            "tur": t.category or "",
        }
        for t in pending_tasks_qs
    ]

    son_rez = list(
        rez_base.only(
            "display_code",
            "primary_guest_name",
            "status",
            "check_in_date",
            "check_out_date",
            "pk",
        ).order_by("-created_at")[:25]
    )
    son_kayitlar = [
        {
            "kod": x.display_code or str(x.pk)[:8],
            "durum": x.status,
            "misafir": x.primary_guest_name or "",
            "giris": str(x.check_in_date),
            "cikis": str(x.check_out_date),
        }
        for x in son_rez
    ]

    bu_hafta_gelen_adet = rez_base.filter(
        status=ReservationStatus.UPCOMING,
        check_in_date__gte=today,
        check_in_date__lte=week_ahead,
    ).count()

    payload = {
        "otel": {
            "kod": hotel.code,
            "ad": hotel.name,
            "sehir": hotel.city or "",
        },
        "veri_tarihi": str(today),
        "sidebar_iceride_ekran_eslemesi": {
            "iceride_gosterilen_sayi": iceride_rezervasyon_sayisi,
            "aciklama": (
                "Masaüstünde 'İÇERİDE / iç misafir' sayacı şu anda "
                "**check-in (checked_in)** durumundaki **rezervasyon adedi**dir; tek rezervasyon = 1. "
                "Bu, kişi sayısı değildir. Kaç rezervasyon var sorusunun cevabı bu sayıdır."
            ),
            "check_in_rezervasyonlarinin_toplam_yetiskin_alani": toplam_yetiskin_alani,
            "aciklama_yetiskin_alani": (
                "`yetiskin_sayi_alani` form alanıdır; yanlış doldurulmuş olabilir. "
                "`iceride_gosterilen_sayi` kullanıcı ekranı ile çelişmez."
            ),
        },
        "odalari": {"toplam": rooms_total, "occupied_etiketi": rooms_occupied},
        "konaklamada_check_in_rezervasyonlari": {
            "aciklama": "status=checked_in (ekrandaki ile aynı küme)",
            "rezervasyon_sayisi": len(konaklamalar),
            "benzersiz_isim_satirlari": unique_person_labels,
            "detaylar": konaklamalar,
        },
        "bugunku_gelis_bekleyen_upcoming": bugun_giris,
        "yedi_gun_gelis_planli_gelecek_sayisi": bu_hafta_gelen_adet,
        "son_rezerve_kayit_ornekleri": son_kayitlar,
        "bekleyen_gorev_ornekleri": bekleyen_gorevler,
        "kurallar": (
            "`sidebar_iceride_ekran_eslemesi`.`iceride_gosterilen_sayi` masaüstündeki İÇERİDE ile aynıdır "
            "(aktif check-in rezervasyon adedi). Bu rakamı yalnızca kullanıcı içeride/otelde kaç kişi "
            "veya eşdeğer bir soru sorduğunda kullan; belirsiz veya alakasız sorularda kendiliğinden doluluk verme. "
            "Kişi/yetişkin ayrımı sorulursa `check_in_rezervasyonlarinin_toplam_yetiskin_alani` ve "
            "`detaylar[].yetiskin_sayi_alani` + isimleri söyle — asla İngilizce 'adult' kullanma. "
            "Sadece bu JSON’daki rakamları kullan; listede olmayan isim uydurma. Sohbetle veritabanına yazma yok."
        ),
    }

    return payload


def reply_inside_guest_count_from_digest(digest: dict[str, Any]) -> str:
    """İçeride sayısı — kısa, net yanıt (LLM yok)."""
    bar = digest["sidebar_iceride_ekran_eslemesi"]
    rcount = int(bar["iceride_gosterilen_sayi"])
    ysum = int(bar["check_in_rezervasyonlarinin_toplam_yetiskin_alani"])
    isimler: list[str] = list(
        digest["konaklamada_check_in_rezervasyonlari"]["benzersiz_isim_satirlari"]
    )

    if rcount == 0:
        return "İÇERİDE: 0."

    bolum = [f"İÇERİDE: {rcount}."]

    if isimler:
        bolum.append(f"Misafir: {', '.join(isimler)}.")

    if ysum != rcount and rcount >= 1:
        bolum.append(f"Kayıtta yazılı toplam yetişkin sayısı: {ysum}.")

    return " ".join(bolum)


def build_hotel_snapshot(hotel_pk: uuid.UUID) -> str:
    return json.dumps(build_hotel_digest(hotel_pk), ensure_ascii=False, indent=2)