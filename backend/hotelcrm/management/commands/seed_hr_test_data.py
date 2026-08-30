"""
İK modülleri için demo personel verisi (Department + StaffMember + hr_profile + StaffAbsenceReport).

Kayıtlar `display_code` prefix `HR-DEMO-` ve `hr_profile['seed_tag'] == 'hr_demo'` ile işaretlenir;
silme yalnızca bu kayıtları hedefler.

Kullanım:
  py manage.py seed_hr_test_data --hotel=DEMO
  py manage.py seed_hr_test_data --hotel=DEMO --wipe-only   # sadece demo İK kayıtlarını sil
  py manage.py seed_hr_test_data --hotel=DEMO --compact     # daha az personel (CI / hızlı)
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hotelcrm.models import Department, Hotel, HotelRecruitment, StaffAbsenceReport, StaffMember
from hotelcrm.models.enums import StaffAbsenceReason, StaffStatus

SEED_TAG = "hr_demo"
def _staff_prefix(hotel_code: str) -> str:
    return f"HR-{(hotel_code or 'DEMO').upper()}-"

DEPARTMENTS: tuple[str, ...] = (
    "Resepsiyon",
    "Kat Hizmetleri",
    "Restoran",
    "Mutfak",
    "Teknik",
    "Yönetim",
    "Güvenlik",
    "SPA",
)

FIRST_NAMES = (
    "Ayşe", "Mehmet", "Zeynep", "Can", "Elif", "Burak", "Selin", "Emre",
    "Deniz", "Cem", "Merve", "Kerem", "Defne", "Onur", "Aslı", "Tolga",
)

LAST_NAMES = (
    "Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Aydın", "Öztürk",
    "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Polat",
)

POSITIONS_BY_DEPT: dict[str, tuple[str, ...]] = {
    "Resepsiyon": ("Resepsiyon Müdürü", "Resepsiyonist", "Şef Resepsiyonist", "Concierge"),
    "Kat Hizmetleri": ("Kat Şefi", "Kat Görevlisi", "Housekeeper", "Çamaşırhane Görevlisi"),
    "Restoran": ("Restoran Müdürü", "Garson", "Komi", "Barmen"),
    "Mutfak": ("Sous Chef", "Aşçı", "Komonist", "Pastacı"),
    "Teknik": ("Teknik Şef", "Tesisatçı", "Elektrikçi", "Bakım Elemanı"),
    "Yönetim": ("Genel Müdür Yardımcısı", "İK Uzmanı", "Muhasebe Sorumlusu"),
    "Güvenlik": ("Güvenlik Şefi", "Güvenlik Görevlisi"),
    "SPA": ("SPA Müdürü", "Terapist", "Resepsiyon (SPA)"),
}

SHIFT_OPTIONS = (
    "Sabah (07:00 – 15:00)",
    "Akşam (15:00 – 23:00)",
    "Gece (23:00 – 07:00)",
    "Tam Gün (09:00 – 18:00)",
)

BLOOD_TYPES = ("A+", "A-", "B+", "O+", "AB+")
MARITAL = ("single", "married", "divorced")
GENDER = ("female", "male", "other")
MILITARY = ("completed", "deferred", "exempt", "na")
CONTRACT_TYPES = ("permanent", "temporary", "seasonal", "parttime", "intern")


def _demo_recruitment_payload(rnd: random.Random, dept_names: tuple[str, ...]) -> dict:
    """İşe alım modülü (HotelRecruitment.data) ile uyumlu demo yapı."""
    today = _today_aware().isoformat()
    d1 = dept_names[0]
    d2 = dept_names[1] if len(dept_names) > 1 else dept_names[0]
    job_recep = str(uuid.uuid4())
    job_cook = str(uuid.uuid4())
    jobs = [
        {
            "id": job_recep,
            "title": "Resepsiyon Görevlisi (demo)",
            "department": d1,
            "position": "Resepsiyonist",
            "employmentType": "fulltime",
            "count": 2,
            "salaryMin": 26000,
            "salaryMax": 34000,
            "location": "Ön büro",
            "description": "Otomatik oluşturuldu (seed_hr_test_data).",
            "requirements": "İngilizce, PMS deneyimi",
            "benefits": "Yemek, servis",
            "publishedAt": today,
            "closedAt": "",
            "status": "open",
        },
        {
            "id": job_cook,
            "title": "Aşçı Yardımcısı (demo)",
            "department": d2,
            "position": "Aşçı",
            "employmentType": "fulltime",
            "count": 1,
            "salaryMin": 32000,
            "salaryMax": 42000,
            "location": "Mutfak",
            "description": "Demo ilan.",
            "requirements": "Hijyen sertifikası",
            "benefits": "",
            "publishedAt": today,
            "closedAt": "",
            "status": "open",
        },
    ]
    samples = [
        ("Demo Aday Bir", "aday1@seed-recruitment.test", "05321110001", job_recep, "new", 30000, 4),
        ("Demo Aday İki", "aday2@seed-recruitment.test", "05321110002", job_recep, "screening", 28000, 3),
        ("Demo Aday Üç", "aday3@seed-recruitment.test", "05321110003", job_cook, "interview1", 38000, 5),
        ("Demo Aday Dört", "aday4@seed-recruitment.test", "05321110004", job_cook, "offer", 40000, 5),
    ]
    candidates = []
    for name, email, phone, job_id, stage, exp_sal, rating in samples:
        candidates.append(
            {
                "id": str(uuid.uuid4()),
                "fullName": name,
                "email": email,
                "phone": phone,
                "jobId": job_id,
                "appliedAt": today,
                "stage": stage,
                "source": rnd.choice(
                    ("Web sitesi", "Kariyer.net", "Referans", "LinkedIn"),
                ),
                "experience": f"{rnd.randint(1, 8)} yıl",
                "expectedSalary": exp_sal,
                "rating": rating,
                "interviews": [],
                "notes": "",
                "cvUrl": "",
            }
        )
    return {"jobs": jobs, "candidates": candidates}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _today_aware() -> date:
    return timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()


def _demo_tckn(rnd: random.Random) -> str:
    """Basit geçerli görünümlü demo TCKN (11 hane)."""
    digits = [rnd.randint(1, 9)] + [rnd.randint(0, 9) for _ in range(8)]
    odd_sum = sum(digits[i] for i in range(0, 9, 2))
    even_sum = sum(digits[i] for i in range(1, 8, 2))
    d10 = ((odd_sum * 7 - even_sum) % 10 + 10) % 10
    digits.append(d10)
    digits.append(sum(digits) % 10)
    return "".join(str(x) for x in digits)


def _build_hr_profile(
    rnd: random.Random,
    *,
    dept_name: str,
    job_title: str,
    hire_date: date,
    monthly: Decimal,
    idx: int,
) -> dict:
    """Frontend `hrHelpers.mergeHrProfile` ile uyumlu anahtarlar."""
    birth = date(hire_date.year - rnd.randint(22, 55), rnd.randint(1, 12), rnd.randint(1, 28))
    gross = float(monthly)
    net = round(gross * 0.72)

    langs = []
    for _ in range(rnd.randint(0, 2)):
        langs.append(
            {
                "id": _uid("lg"),
                "lang": rnd.choice(("İngilizce", "Almanca", "Rusça", "Arapça", "Fransızca")),
                "level": rnd.choice(("A2", "B1", "B2", "C1", "C2")),
            }
        )

    children = []
    if rnd.random() < 0.35:
        children.append(
            {
                "id": _uid("ch"),
                "name": f"{rnd.choice(FIRST_NAMES)} {rnd.choice(LAST_NAMES)}",
                "birthDate": (birth + timedelta(days=365 * rnd.randint(2, 12))).isoformat(),
            }
        )

    emergencies = []
    if rnd.random() < 0.85:
        emergencies.append(
            {
                "id": _uid("em"),
                "name": f"{rnd.choice(FIRST_NAMES)} {rnd.choice(LAST_NAMES)}",
                "relation": rnd.choice(("Eş", "Anne", "Baba", "Kardeş")),
                "phone": f"05{rnd.randint(30, 59)}{rnd.randint(1000000, 9999999)}",
            }
        )

    documents = [
        {
            "id": _uid("doc"),
            "name": "SGK işe giriş bildirgesi",
            "type": "sgk",
            "expiry": "",
            "note": "Arşivde",
        },
        {
            "id": _uid("doc"),
            "name": "Hijyen eğitimi sertifikası",
            "type": "license",
            "expiry": (_today_aware() + timedelta(days=rnd.randint(30, 400))).isoformat(),
            "note": "Otel içi eğitim",
        },
    ]

    leave_requests = []
    for _ in range(rnd.randint(0, 3)):
        s = hire_date + timedelta(days=rnd.randint(60, 400))
        days = rnd.randint(1, 5)
        e = s + timedelta(days=days - 1)
        leave_requests.append(
            {
                "id": _uid("lv"),
                "type": rnd.choice(("annual", "sick", "excused", "education", "bereavement")),
                "startDate": s.isoformat(),
                "endDate": e.isoformat(),
                "days": float(days),
                "halfDay": False,
                "reason": rnd.choice(("", "Aile ziyareti", "Sağlık", "Okul")),
                "status": rnd.choice(("approved", "approved", "pending", "rejected")),
                "createdAt": (s - timedelta(days=rnd.randint(1, 14))).isoformat() + "Z",
                "decidedBy": "İK" if rnd.random() > 0.2 else "",
                "decidedAt": (s - timedelta(days=1)).isoformat() + "Z" if rnd.random() > 0.3 else "",
            }
        )

    trainings = []
    for _ in range(rnd.randint(1, 4)):
        tstart = hire_date + timedelta(days=rnd.randint(10, 200))
        trainings.append(
            {
                "id": _uid("tr"),
                "title": rnd.choice(
                    (
                        "İSG temel eğitimi",
                        "Hijyen ve HACCP",
                        "Misafir memnuniyeti",
                        "Yangın tatbikatı",
                        "İlk yardım",
                    )
                ),
                "provider": rnd.choice(("İSG Akademi", "Otel içi", "Belediye", "MEB onaylı kurum")),
                "type": rnd.choice(("mandatory", "internal", "certificate", "onboarding")),
                "startDate": tstart.isoformat(),
                "endDate": (tstart + timedelta(days=rnd.randint(0, 2))).isoformat(),
                "status": rnd.choice(("completed", "completed", "inprogress", "planned")),
                "score": rnd.randint(70, 98),
                "certificateNo": f"CRT-{rnd.randint(10000, 99999)}" if rnd.random() > 0.4 else "",
                "expiry": (tstart + timedelta(days=365)).isoformat() if rnd.random() > 0.5 else "",
                "cost": rnd.randint(0, 2500),
                "notes": "",
            }
        )

    evaluations = []
    if idx % 3 != 0:
        period = f"{hire_date.year}-H2" if rnd.random() > 0.5 else f"{hire_date.year}-H1"
        scores = {
            "quality": rnd.randint(65, 95),
            "productivity": rnd.randint(60, 92),
            "attendance": rnd.randint(70, 98),
            "teamwork": rnd.randint(68, 94),
            "guest": rnd.randint(72, 96),
            "initiative": rnd.randint(55, 90),
            "communication": rnd.randint(65, 93),
        }
        wsum = sum(
            scores[k] * w
            for k, w in (
                ("quality", 20),
                ("productivity", 15),
                ("attendance", 15),
                ("teamwork", 15),
                ("guest", 15),
                ("initiative", 10),
                ("communication", 10),
            )
        )
        overall = round(wsum / 100)
        evaluations.append(
            {
                "id": _uid("ev"),
                "period": period,
                "evaluator": rnd.choice(("İK Müdürü", "Departman Müdürü", "GM Yardımcısı")),
                "date": (hire_date + timedelta(days=300)).isoformat(),
                "scores": scores,
                "overall": overall,
                "strengths": rnd.choice(
                    ("Misafir odaklı, ekip uyumu güçlü.", "Disiplinli ve dakik.", "Çözüm üretir.")
                ),
                "improvements": rnd.choice(
                    ("Raporlama düzeni geliştirilebilir.", "İngilizce pratik.", "Stres yönetimi.")
                ),
                "goals": "Yıllık sertifika programını tamamlamak.",
                "notes": "Demo değerlendirme.",
            }
        )

    disciplinary = []
    if rnd.random() < 0.12:
        disciplinary.append(
            {
                "id": _uid("dc"),
                "type": rnd.choice(("verbal", "written")),
                "date": (_today_aware() - timedelta(days=rnd.randint(20, 120))).isoformat(),
                "reason": "Geç kalma tekrarı",
                "description": "Vardiya öncesi 15 dk gecikme bildirimi.",
                "issuer": "Departman Müdürü",
                "witnessName": "",
                "resolved": rnd.choice((True, False)),
            }
        )

    advances = []
    if rnd.random() < 0.25:
        advances.append(
            {
                "id": _uid("adv"),
                "date": (_today_aware() - timedelta(days=rnd.randint(5, 40))).isoformat(),
                "amount": rnd.choice((1500, 2500, 4000, 8000)),
                "notes": "Acil sağlık gideri",
                "recoveredAt": "" if rnd.random() > 0.5 else (_today_aware() - timedelta(days=1)).isoformat(),
            }
        )

    payrolls = []
    y, m = _today_aware().year, _today_aware().month
    for back in range(3):
        mm = m - back
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        month_key = f"{yy}-{mm:02d}"
        sgk_base = gross + rnd.randint(0, 800)
        sgk_r = round(sgk_base * 0.14)
        unemp = round(sgk_base * 0.01)
        inc_base = max(0, sgk_base - sgk_r - unemp)
        inc_tax = round(inc_base * 0.15)
        stamp = round(sgk_base * 0.00759)
        adv_cut = rnd.randint(0, 2000) if advances and rnd.random() > 0.6 else 0
        other = rnd.randint(0, 500)
        total_d = sgk_r + unemp + inc_tax + stamp + adv_cut + other
        net_pay = round(sgk_base - total_d)
        payrolls.append(
            {
                "id": _uid("pr"),
                "month": month_key,
                "gross": sgk_base,
                "bonus": rnd.randint(0, 1500) if rnd.random() > 0.7 else 0,
                "overtime": rnd.randint(0, 1200) if rnd.random() > 0.65 else 0,
                "sgk": sgk_r,
                "unemployment": unemp,
                "incomeTax": inc_tax,
                "stampTax": stamp,
                "advance": adv_cut,
                "otherDeductions": other,
                "totalDeductions": total_d,
                "net": net_pay,
                "notes": "",
                "paidAt": (date(yy, mm, 28).isoformat() + "T10:00:00Z") if back > 0 or rnd.random() > 0.3 else "",
            }
        )

    shifts: dict[str, str] = {}
    d0 = _today_aware() - timedelta(days=_today_aware().weekday())
    codes = ("morning", "evening", "night", "fullday", "off", "leave", "training")
    for i in range(7):
        shifts[(d0 + timedelta(days=i)).isoformat()] = rnd.choice(codes)

    used_annual = sum(
        int(r.get("days", 0))
        for r in leave_requests
        if r.get("status") == "approved" and r.get("type") == "annual"
    )

    return {
        "seed_tag": SEED_TAG,
        "personal": {
            "birthDate": birth.isoformat(),
            "birthPlace": rnd.choice(("İstanbul", "Ankara", "İzmir", "Antalya", "Bursa")),
            "gender": rnd.choice(GENDER),
            "maritalStatus": rnd.choice(MARITAL),
            "bloodType": rnd.choice(BLOOD_TYPES),
            "childrenCount": len(children),
            "nationality": "TR",
            "driverLicense": rnd.choice(("", "B", "B, BE")),
            "militaryStatus": rnd.choice(MILITARY),
        },
        "contact": {
            "address": f"{rnd.choice(('Atatürk', 'Cumhuriyet', 'İnönü'))} Mah. No:{rnd.randint(1, 120)}",
            "city": rnd.choice(("İstanbul", "Ankara", "Antalya")),
            "district": rnd.choice(("Kadıköy", "Çankaya", "Muratpaşa", "Nilüfer")),
            "postalCode": f"{rnd.randint(34000, 34999)}",
            "workEmail": f"demo.{idx}@demo-hotel.local",
            "workPhone": f"0212 {rnd.randint(200, 899)} {rnd.randint(1000, 9999)}",
        },
        "job": {
            "contractType": rnd.choice(CONTRACT_TYPES),
            "employmentType": rnd.choice(("fulltime", "fulltime", "parttime")),
            "workType": rnd.choice(("onsite", "hybrid", "onsite")),
            "sgkNumber": f"{rnd.randint(100000000, 999999999)}",
            "sgkStartDate": hire_date.isoformat(),
            "probationEndDate": (hire_date + timedelta(days=90)).isoformat(),
            "reportsTo": rnd.choice(("Genel Müdür", "Operasyon Müdürü", f"{dept_name} Müdürü")),
            "badgeNumber": f"B-{1000 + idx:04d}",
            "costCenter": f"CC-{dept_name[:3].upper()}-{rnd.randint(1, 9)}",
        },
        "salary": {
            "gross": gross,
            "net": net,
            "hourlyRate": round(gross / 225, 2),
            "bankName": rnd.choice(("Ziraat Bankası", "İş Bankası", "Garanti BBVA", "Akbank")),
            "iban": "TR"
            + "".join(str(rnd.randint(0, 9)) for _ in range(24)),
            "paymentDay": rnd.choice((1, 5, 15, 25)),
            "taxOffice": rnd.choice(("Kadıköy", "Beşiktaş", "Çankaya")),
            "sgkRiskClass": rnd.choice(("II", "III", "II-1")),
        },
        "education": {
            "level": rnd.choice(("Lise", "Önlisans", "Lisans", "Yüksek lisans")),
            "schoolName": rnd.choice(("Turizm Otelcilik MYO", "Akdeniz Üniversitesi", "Marmara Üniversitesi")),
            "graduationYear": str(hire_date.year - rnd.randint(0, 8)),
            "department": rnd.choice(("Turizm İşletmeciliği", "Gastronomi", "İşletme")),
            "languages": langs,
        },
        "emergencyContacts": emergencies,
        "family": {
            "spouseName": rnd.choice(("", f"{rnd.choice(FIRST_NAMES)} {rnd.choice(LAST_NAMES)}")),
            "children": children,
        },
        "documents": documents,
        "leaveBalance": {
            "annual": rnd.choice((14, 20, 26)),
            "carriedOver": rnd.choice((0, 0, 2, 5)),
            "used": used_annual,
        },
        "leaveRequests": leave_requests,
        "trainings": trainings,
        "evaluations": evaluations,
        "disciplinary": disciplinary,
        "advances": advances,
        "payrolls": payrolls,
        "shifts": shifts,
        "notes": "Bu kayıt seed_hr_test_data ile oluşturulmuştur (demo).",
        "terminationDate": "",
        "terminationReason": "",
    }


class Command(BaseCommand):
    help = "İK modülleri için demo departman, personel (hr_profile) ve örnek devamsızlık kayıtları."

    def add_arguments(self, parser):
        parser.add_argument("--hotel", default="DEMO", help="Otel code")
        parser.add_argument(
            "--wipe-only",
            action="store_true",
            help="Sadece demo İK kayıtlarını sil, yeniden oluşturma.",
        )
        parser.add_argument(
            "--compact",
            action="store_true",
            help="Daha az personel (CI / hızlı demo).",
        )

    def handle(self, *args, **options):
        code = options["hotel"]
        hotel = Hotel.objects.filter(code=code).first()
        if not hotel:
            self.stdout.write(self.style.ERROR(f"Otel bulunamadı: code={code!r}"))
            return

        n_removed = self._clear_seed(hotel)
        if n_removed:
            self.stdout.write(f"Silinen demo personel: {n_removed}")

        if options["wipe_only"]:
            self.stdout.write(self.style.SUCCESS("İK demo verisi temizlendi (--wipe-only)."))
            return

        rnd = random.Random(20260514)
        compact = bool(options["compact"])
        staff_count = 10 if compact else 28

        with transaction.atomic():
            dept_map: dict[str, Department] = {}
            for name in DEPARTMENTS:
                dept, _ = Department.objects.get_or_create(
                    hotel=hotel,
                    name=name,
                )
                dept_map[name] = dept

            today = _today_aware()
            created_staff: list[StaffMember] = []

            for i in range(staff_count):
                dept_name = DEPARTMENTS[i % len(DEPARTMENTS)]
                dept = dept_map[dept_name]
                titles = POSITIONS_BY_DEPT.get(dept_name, ("Personel",))
                job_title = titles[i % len(titles)]
                hire_date = today - timedelta(days=rnd.randint(120, 2200))
                monthly = Decimal(str(rnd.randint(24000, 78000)))
                idx = i + 1
                display_code = f"{_staff_prefix(code)}{idx:03d}"
                first = rnd.choice(FIRST_NAMES)
                last = rnd.choice(LAST_NAMES)
                full_name = f"{first} {last}"

                status = StaffStatus.ACTIVE
                if i % 11 == 0:
                    status = StaffStatus.ON_LEAVE
                elif i % 17 == 0:
                    status = StaffStatus.INACTIVE

                profile = _build_hr_profile(
                    rnd,
                    dept_name=dept_name,
                    job_title=job_title,
                    hire_date=hire_date,
                    monthly=monthly,
                    idx=idx,
                )

                sm = StaffMember.objects.create(
                    hotel=hotel,
                    department=dept,
                    display_code=display_code,
                    full_name=full_name,
                    job_title=job_title,
                    shift_window=rnd.choice(SHIFT_OPTIONS),
                    status=status,
                    phone=f"05{rnd.randint(30, 59)}{rnd.randint(1000000, 9999999)}",
                    email=f"personel{idx}@seed-hr.{code.lower()}.test",
                    national_id=_demo_tckn(rnd),
                    hire_date=hire_date,
                    monthly_wage=monthly,
                    hr_profile=profile,
                )
                created_staff.append(sm)

            abs_reasons = [c[0] for c in StaffAbsenceReason.choices]
            n_abs = 0
            k_sample = min(12, len(created_staff))
            if k_sample > 0:
                for sm in rnd.sample(created_staff, k=k_sample):
                    for _ in range(rnd.randint(1, 3)):
                        abs_day = today - timedelta(days=rnd.randint(1, 90))
                        StaffAbsenceReport.objects.create(
                            hotel=hotel,
                            staff_member=sm,
                            absence_date=abs_day,
                            reason=rnd.choice(abs_reasons),
                            notes="Demo devamsızlık (seed_hr_test_data)",
                        )
                        n_abs += 1

            if not HotelRecruitment.objects.filter(hotel=hotel).exists():
                HotelRecruitment.objects.create(
                    hotel=hotel,
                    data=_demo_recruitment_payload(rnd, DEPARTMENTS),
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"İK demo verisi: {hotel.code} — {len(created_staff)} personel, "
                f"{n_abs} yeni demo devamsızlık kaydı"
            )
        )

    def _clear_seed(self, hotel: Hotel) -> int:
        """Demo personeli siler: display_code HR-DEMO-* veya hr_profile.seed_tag."""
        id_set: set = set(
            StaffMember.objects.filter(
                hotel=hotel,
                display_code__startswith=_staff_prefix(hotel.code),
            ).values_list("pk", flat=True),
        )
        # SQLite JSON contains desteklemez; seed_tag el ile taranır.
        for pk, prof in StaffMember.objects.filter(hotel=hotel).values_list(
            "id", "hr_profile",
        ):
            if isinstance(prof, dict) and prof.get("seed_tag") == SEED_TAG:
                id_set.add(pk)
        n = len(id_set)
        if n:
            StaffMember.objects.filter(pk__in=id_set).delete()
        return n
