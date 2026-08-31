"""
Otel için toplu test verisi: oda tipleri, çok sayıda oda, ~1 yıllık rezervasyon geçmişi,
oda-gecesi bazında folio + ödeme + kasa geliri; ayrıca yıl boyunca gider hareketleri.

Kullanım:
  py manage.py seed_pms_test_data --hotel=DEMO
  py manage.py seed_pms_test_data --hotel=DEMO --wipe
  py manage.py seed_pms_test_data --hotel=DEMO --wipe --compact
    (Vercel/CI: az oda ve rezervasyon; build icin hizli)

İşaretler: room_type SEED_*; guest *@seed.hotelcrm.test (TR: demo TCKN; diğer uyruklar: demo pasaport);
reservation notes [seed-pms-test]; kasa satırları description içinde [seed-cash].

Komut sonunda `seed_hr_test_data` çağrılır (display_code HR-DEMO-*, zengin hr_profile + örnek eksiklik kayıtları).
"""

from __future__ import annotations

import random
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from hotelcrm.models import (
    CashTransaction,
    Channel,
    Folio,
    FolioLine,
    Guest,
    Hotel,
    Payment,
    Reservation,
    ReservationOccupant,
    Room,
    RoomType,
)
from hotelcrm.models.enums import (
    BoardBasis,
    CashFlowType,
    FolioLineType,
    HousekeepingCleanStatus,
    PaymentMethod,
    ReservationStatus,
    RoomOccupancyStatus,
)

SEED_NOTE = "[seed-pms-test]"
SEED_EMAIL_SUFFIX = "@seed.hotelcrm.test"
SEED_RT_PREFIX = "SEED_"
SEED_CASH_TAG = "[seed-cash]"

FIRST_NAMES = (
    "Ayşe",
    "Mehmet",
    "Zeynep",
    "Can",
    "Elif",
    "Burak",
    "Selin",
    "Emre",
    "Deniz",
    "Cem",
    "Merve",
    "Kerem",
    "Defne",
    "Onur",
    "Aslı",
    "Tolga",
    "Gizem",
    "Barış",
    "Nazlı",
    "Serkan",
    "Pınar",
    "Utku",
    "Büşra",
    "Kaan",
    "İrem",
    "Arda",
    "Sude",
    "Eren",
    "Melis",
    "Yasin",
)

LAST_NAMES = (
    "Yılmaz",
    "Kaya",
    "Demir",
    "Şahin",
    "Çelik",
    "Yıldız",
    "Aydın",
    "Öztürk",
    "Arslan",
    "Doğan",
    "Kılıç",
    "Aslan",
    "Çetin",
    "Kara",
    "Koç",
    "Polat",
    "Erdoğan",
    "Aksoy",
    "Bulut",
    "Güneş",
)

ROOM_TYPE_DEFS = (
    ("SEED_STD", "Standart", Decimal("2400"), 2),
    ("SEED_STD_PAN", "Standart Deniz Manzaralı", Decimal("2900"), 2),
    ("SEED_DLX", "Deluxe", Decimal("3500"), 2),
    ("SEED_JST", "Junior Süit", Decimal("4200"), 3),
    ("SEED_STE", "Süit", Decimal("5500"), 4),
    ("SEED_FAM", "Aile Odası", Decimal("4800"), 5),
    ("SEED_ECO", "Ekonomi Tek", Decimal("1800"), 1),
    ("SEED_ACC", "Engelsiz Oda", Decimal("2600"), 2),
)

TAX_RATE = Decimal("0.10")
WEEKEND_BUMP = Decimal("1.12")


def d0(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def unique_cash_code() -> str:
    return f"SC{uuid.uuid4().hex[:14].upper()}"


def generate_valid_demo_tckn(rnd: random.Random) -> str:
    """11 haneli doğrulanabilir TCKN (demo). Frontend `trTaxId.isValidTckn` ile uyumlu."""

    digits = [rnd.randint(1, 9)] + [rnd.randint(0, 9) for _ in range(8)]
    odd_sum = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
    even_sum = digits[1] + digits[3] + digits[5] + digits[7]
    d10 = ((odd_sum * 7 - even_sum) % 10 + 10) % 10
    digits.append(d10)
    digits.append(sum(digits) % 10)
    return "".join(str(x) for x in digits)


# ISO 3166-1 alpha-2 (Guest.nationality max 2 karakter). Olasılıklar tohum çeşitliliği içindir.
SEED_NATIONALITY_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("TR", 0.58),
    ("DE", 0.08),
    ("GB", 0.06),
    ("US", 0.06),
    ("FR", 0.05),
    ("IT", 0.04),
    ("NL", 0.03),
    ("ES", 0.03),
    ("SA", 0.02),
    ("AE", 0.02),
    ("RU", 0.02),
    ("PL", 0.01),
)


def pick_seed_nationality(rnd: random.Random) -> str:
    codes, weights = zip(*SEED_NATIONALITY_WEIGHTS, strict=True)
    return rnd.choices(codes, weights=weights, k=1)[0]


def generate_demo_passport_no(nationality: str, rnd: random.Random) -> str:
    """Ülkeye göre karışık biçimde demo pasaport numarası (gerçek değildir)."""
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    L = lambda: rnd.choice(letters)
    dig = lambda n: "".join(str(rnd.randint(0, 9)) for _ in range(n))

    if nationality == "DE":
        raw = f"{L()}{dig(8)}{rnd.randint(0, 9)}"
    elif nationality == "GB":
        raw = f"{rnd.randint(100000000, 999999999)}{L()}"
    elif nationality == "US":
        raw = dig(9)
    elif nationality == "FR":
        raw = f"{rnd.randint(10, 99)}{L()}{rnd.randint(10, 99)}{dig(5)}"
    elif nationality == "IT":
        raw = f"{L()}{L()}{dig(7)}"
    elif nationality == "NL":
        raw = f"{L()}{L()}{dig(8)}"
    elif nationality == "ES":
        raw = f"{L()}{dig(8)}"
    elif nationality == "SA":
        raw = f"{L()}{dig(8)}"
    elif nationality == "AE":
        raw = dig(10)
    elif nationality == "RU":
        raw = f"{rnd.randint(1000, 9999)}{dig(6)}"
    elif nationality == "PL":
        raw = f"{L()}{L()}{dig(7)}"
    else:
        raw = f"{nationality}{rnd.randint(100000, 999999)}{L()}{L()}"
    return raw[:32]


class Command(BaseCommand):
    help = "1 yıllık senaryo: çok oda, çok rezervasyon, folio+ödeme+kasa+gider tohumu."

    def add_arguments(self, parser):
        parser.add_argument("--hotel", default="DEMO", help="Otel code")
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Önceki PMS tohum kayıtlarını sil, sonra yeniden üret.",
        )
        parser.add_argument(
            "--compact",
            action="store_true",
            help="Vercel/CI icin kucuk veri seti (az oda, misafir, rezervasyon).",
        )

    def handle(self, *args, **options):
        code = options["hotel"]
        hotel = Hotel.objects.filter(code=code).first()
        if not hotel:
            self.stdout.write(self.style.ERROR(f"Otel bulunamadı: code={code!r}"))
            return

        if options["wipe"]:
            self._wipe(hotel)

        rnd = random.Random(20260211)
        today = timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()

        compact = bool(options["compact"])
        per_type = 1 if compact else 20
        guest_n = 12 if compact else 240

        with transaction.atomic():
            room_types = self._seed_room_types(hotel)
            rooms = self._seed_rooms(hotel, room_types, rnd, per_type=per_type)
            channels = self._ensure_channels(hotel)
            guests = self._seed_guests(hotel, rnd, count=guest_n)
            occ = RoomOccupancyTracker(rooms)
            n_res, n_pay, n_cash_in, n_cash_ex = self._seed_year_scenario(
                hotel=hotel,
                rooms=rooms,
                room_types=room_types,
                channels=channels,
                guests=guests,
                occ=occ,
                today=today,
                rnd=rnd,
                compact=compact,
            )
            self._sync_guest_totals(hotel, guests)
            self._sync_room_occupancy_from_active_stays(hotel)

        self.stdout.write(
            self.style.SUCCESS(
                f"Tamam: {hotel.code} — {len(rooms)} oda, {len(guests)} misafir, "
                f"{n_res} rezervasyon, {n_pay} ödeme kaydı, kasa gelir={n_cash_in} gider={n_cash_ex}"
            )
        )

        call_command("seed_hr_test_data", hotel=code, compact=compact)
        self.stdout.write(self.style.SUCCESS(f"İK demo personeli senkron: {code}"))

    def _wipe(self, hotel: Hotel) -> None:
        res_q = Reservation.objects.filter(hotel=hotel, notes__contains=SEED_NOTE)
        res_ids = list(res_q.values_list("id", flat=True))
        n_res = len(res_ids)

        Payment.objects.filter(reservation_id__in=res_ids).delete()
        Folio.objects.filter(reservation_id__in=res_ids).delete()
        res_q.delete()

        CashTransaction.objects.filter(hotel=hotel, description__contains=SEED_CASH_TAG).delete()

        n_g = Guest.objects.filter(hotel=hotel, email__iendswith=SEED_EMAIL_SUFFIX).delete()[0]
        n_rm = Room.objects.filter(hotel=hotel, room_type__code__startswith=SEED_RT_PREFIX).delete()[0]
        n_rt = RoomType.objects.filter(hotel=hotel, code__startswith=SEED_RT_PREFIX).delete()[0]

        self.stdout.write(
            f"Silindi: rezervasyon={n_res}, misafir={n_g}, oda={n_rm}, oda tipi={n_rt}"
        )

    def _seed_room_types(self, hotel: Hotel) -> list[RoomType]:
        out: list[RoomType] = []
        for code, name, default_rate, max_occ in ROOM_TYPE_DEFS:
            rt, _ = RoomType.objects.get_or_create(
                hotel=hotel,
                code=code,
                defaults={
                    "name": name,
                    "default_rate": default_rate,
                    "max_occupancy": max_occ,
                },
            )
            out.append(rt)
        return out

    def _seed_rooms(
        self,
        hotel: Hotel,
        room_types: list[RoomType],
        rnd: random.Random,
        *,
        per_type: int,
    ) -> list[Room]:
        rooms: list[Room] = []
        used: set[str] = set(Room.objects.filter(hotel=hotel).values_list("room_number", flat=True))
        for rt in room_types:
            for _i in range(per_type):
                for _guard in range(400):
                    floor = rnd.randint(1, 14)
                    suf = rnd.randint(1, 99)
                    extra = rnd.randint(0, 9)
                    num = f"{floor}{suf:02d}{extra}"
                    if num not in used:
                        used.add(num)
                        rooms.append(
                            Room.objects.create(
                                hotel=hotel,
                                room_type=rt,
                                room_number=num,
                                floor=floor,
                                occupancy_status=RoomOccupancyStatus.VACANT,
                                clean_status=HousekeepingCleanStatus.CLEAN,
                            )
                        )
                        break
        return rooms

    def _ensure_channels(self, hotel: Hotel) -> list[Channel]:
        specs = [
            ("Direkt", "DIRECT"),
            ("Booking.com", "BKG"),
            ("Expedia", "EXP"),
            ("Acenta B2B", "AGB2B"),
            ("Hotel Web", "WEB"),
        ]
        out: list[Channel] = []
        for name, ccode in specs:
            ch, _ = Channel.objects.get_or_create(
                hotel=hotel,
                code=ccode,
                defaults={"name": name},
            )
            out.append(ch)
        return out

    def _seed_guests(self, hotel: Hotel, rnd: random.Random, count: int) -> list[Guest]:
        guests: list[Guest] = []
        used_tckn: set[str] = set()
        used_passport: set[str] = set()
        for i in range(count):
            fn = rnd.choice(FIRST_NAMES)
            ln = rnd.choice(LAST_NAMES)
            nationality = pick_seed_nationality(rnd)
            national_id = ""
            passport_no = ""

            if nationality == "TR":
                for _attempt in range(80):
                    tckn = generate_valid_demo_tckn(rnd)
                    if tckn not in used_tckn:
                        used_tckn.add(tckn)
                        national_id = tckn
                        break
            else:
                for _attempt in range(80):
                    pno = generate_demo_passport_no(nationality, rnd)
                    if pno and pno not in used_passport:
                        used_passport.add(pno)
                        passport_no = pno
                        break

            guests.append(
                Guest.objects.create(
                    hotel=hotel,
                    first_name=fn,
                    last_name=ln,
                    email=f"seed.{hotel.code.lower()}.{i}{SEED_EMAIL_SUFFIX}",
                    phone=f"+9053{rnd.randint(100, 999)}{rnd.randint(1000, 9999)}",
                    nationality=nationality,
                    national_id=national_id,
                    passport_no=passport_no,
                    visit_count=0,
                    total_spent=Decimal("0"),
                )
            )
        return guests

    def _nightly_rate(self, rt: RoomType, day: date, rnd: random.Random) -> Decimal:
        base = Decimal(rt.default_rate or Decimal("2000"))
        w = day.weekday()
        if w >= 5:
            base = d0(base * WEEKEND_BUMP)
        jitter = d0(base * (Decimal("0.97") + Decimal(str(rnd.random() * 0.06))))
        return max(jitter, Decimal("500"))

    def _board_supplement_per_night(self, board: str) -> Decimal:
        if board == BoardBasis.HB:
            return Decimal("350")
        if board == BoardBasis.AI:
            return Decimal("750")
        return Decimal("0")

    def _compute_stay_charges(
        self,
        rt: RoomType,
        check_in: date,
        check_out: date,
        board: str,
        adults: int,
        rnd: random.Random,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Konaklama satırı, vergi, ekstra, toplam (ekstra+hariç vergi öncesi konaklama)."""
        nights = max((check_out - check_in).days, 1)
        room_total = Decimal("0")
        d = check_in
        for _ in range(nights):
            room_total += self._nightly_rate(rt, d, rnd)
            d += timedelta(days=1)
        board_extra = self._board_supplement_per_night(board) * nights
        room_total = d0(room_total)
        board_extra = d0(board_extra)
        extras = Decimal("0")
        if rnd.random() < 0.28:
            extras = d0(Decimal(str(rnd.randint(2, 8) * 150)))
        occ_extra = d0(Decimal(max(0, adults - 2)) * Decimal("120") * nights) if adults > 2 else Decimal("0")
        extras = d0(extras + occ_extra)
        sub_before_tax = d0(room_total + board_extra + extras)
        tax = d0(sub_before_tax * TAX_RATE)
        grand = d0(sub_before_tax + tax)
        return sub_before_tax, tax, extras, grand

    def _pick_room(
        self,
        occ: RoomOccupancyTracker,
        rt: RoomType,
        check_in: date,
        check_out: date,
        rnd: random.Random,
    ) -> Room | None:
        pool = occ.rooms_for_type(rt.id)
        if not pool:
            return None
        rnd.shuffle(pool)
        for r in pool[: min(40, len(pool))]:
            if occ.can_book(r.id, check_in, check_out):
                return r
        return None

    def _pick_any_available_room(
        self,
        occ: RoomOccupancyTracker,
        check_in: date,
        check_out: date,
        rnd: random.Random,
    ) -> Room | None:
        """Aynı otelde, tarihlerde çakışma yoksa herhangi bir boş oda (tip uyuşmazlığında demo için)."""
        candidates = [
            r for r in occ.all_rooms_list if occ.can_book(r.id, check_in, check_out)
        ]
        if not candidates:
            return None
        return rnd.choice(candidates)

    def _seed_year_scenario(
        self,
        hotel: Hotel,
        rooms: list[Room],
        room_types: list[RoomType],
        channels: list[Channel],
        guests: list[Guest],
        occ: RoomOccupancyTracker,
        today: date,
        rnd: random.Random,
        *,
        compact: bool = False,
    ) -> tuple[int, int, int, int]:
        created_res = 0
        if compact:
            year_ago = today - timedelta(days=45)
            n_completed = 8
            n_cancel = 1
            n_inhouse = 3
            future_spans: tuple[tuple[int, int, int], ...] = (
                (1, 21, 4),
                (22, 45, 3),
            )
            expense_day_prob = 0.08
        else:
            year_ago = today - timedelta(days=365)
            n_completed = 920
            n_cancel = 95
            n_inhouse = 26
            future_spans = (
                (1, 120, 260),
                (121, 400, 200),
            )
            expense_day_prob = 0.42

        # --- Tamamlanmis konaklamalar (genis veya dar tarih penceresi) ---
        window_days = (today - year_ago).days
        for _ in range(n_completed):
            nights = rnd.randint(1, 12)
            check_out = year_ago + timedelta(days=rnd.randint(nights + 1, max(window_days, nights + 2)))
            if check_out >= today:
                check_out = today - timedelta(days=rnd.randint(1, 5))
            check_in = check_out - timedelta(days=nights)
            if check_in < year_ago - timedelta(days=14):
                check_in = year_ago
            nights = max((check_out - check_in).days, 1)
            rt = rnd.choice(room_types)
            room = self._pick_room(occ, rt, check_in, check_out, rnd)
            if room:
                occ.add(room.id, check_in, check_out)
            g = rnd.choice(guests)
            board = rnd.choice([BoardBasis.BB, BoardBasis.HB, BoardBasis.AI])
            adults = rnd.randint(1, min(4, rt.max_occupancy or 2))
            sub, tax, extras_raw, grand = self._compute_stay_charges(
                rt, check_in, check_out, board, adults, rnd
            )
            split_bill = rnd.random() < 0.07
            if split_bill:
                bal = d0(Decimal(str(rnd.choice([80, 120, 200, 350]))))
                paid = d0(grand - bal)
            else:
                bal = Decimal("0")
                paid = grand
            res = Reservation.objects.create(
                hotel=hotel,
                guest=g,
                primary_guest_name=f"{g.first_name} {g.last_name}".strip(),
                room=room,
                room_type=rt,
                channel=rnd.choice(channels),
                check_in_date=check_in,
                check_out_date=check_out,
                nights=nights,
                adults=adults,
                status=ReservationStatus.CHECKED_OUT,
                board_basis=board,
                total_amount=grand,
                paid_amount=paid,
                balance_amount=bal,
                notes=f"Konaklama tamamlandı. {SEED_NOTE}",
            )
            self._write_folio_and_payments(
                hotel,
                res,
                rt,
                check_in,
                check_out,
                nights,
                board,
                sub,
                tax,
                extras_raw,
                grand,
                paid,
                bal,
                rnd,
            )
            ReservationOccupant.objects.create(
                reservation=res, guest=g, is_primary=True, sequence=0
            )
            created_res += 1

        # --- İptaller ---
        cancel_window = min(300, max(30, window_days - 10))
        for _ in range(n_cancel):
            nights = rnd.randint(2, 8)
            check_in = year_ago + timedelta(days=rnd.randint(10, cancel_window))
            check_out = check_in + timedelta(days=nights)
            rt = rnd.choice(room_types)
            g = rnd.choice(guests)
            sub, tax, _ex, grand = self._compute_stay_charges(
                rt, check_in, check_out, BoardBasis.BB, 2, rnd
            )
            Reservation.objects.create(
                hotel=hotel,
                guest=g,
                primary_guest_name=f"{g.first_name} {g.last_name}".strip(),
                room=None,
                room_type=rt,
                channel=rnd.choice(channels),
                check_in_date=check_in,
                check_out_date=check_out,
                nights=nights,
                adults=2,
                status=ReservationStatus.CANCELLED,
                board_basis=BoardBasis.BB,
                total_amount=grand,
                paid_amount=Decimal("0"),
                balance_amount=grand,
                notes=f"İptal. {SEED_NOTE}",
            )
            created_res += 1

        # --- İçeride ---
        for _ in range(n_inhouse):
            nights = rnd.randint(4, 16)
            check_in = today - timedelta(days=rnd.randint(0, 6))
            check_out = check_in + timedelta(days=nights)
            if check_out <= today:
                check_out = today + timedelta(days=rnd.randint(2, 8))
                nights = max((check_out - check_in).days, 1)
            rt = rnd.choice(room_types)
            room = self._pick_room(occ, rt, check_in, check_out, rnd)
            if not room:
                room = rnd.choice(occ.all_rooms_list)
            occ.add(room.id, check_in, check_out)
            g = rnd.choice(guests)
            board = BoardBasis.BB
            adults = rnd.randint(1, 2)
            sub, tax, extras_raw, grand = self._compute_stay_charges(
                rt, check_in, check_out, board, adults, rnd
            )
            dep_ratio = Decimal(str(rnd.uniform(0.25, 0.55)))
            paid = d0(grand * dep_ratio)
            bal = d0(grand - paid)
            res = Reservation.objects.create(
                hotel=hotel,
                guest=g,
                primary_guest_name=f"{g.first_name} {g.last_name}".strip(),
                room=room,
                room_type=rt,
                channel=rnd.choice(channels),
                check_in_date=check_in,
                check_out_date=check_out,
                nights=nights,
                adults=adults,
                status=ReservationStatus.CHECKED_IN,
                board_basis=board,
                total_amount=grand,
                paid_amount=paid,
                balance_amount=bal,
                notes=f"Konaklıyor. {SEED_NOTE}",
            )
            self._write_folio_and_payments(
                hotel,
                res,
                rt,
                check_in,
                check_out,
                nights,
                board,
                sub,
                tax,
                extras_raw,
                grand,
                paid,
                bal,
                rnd,
                closed=False,
            )
            ReservationOccupant.objects.create(
                reservation=res, guest=g, is_primary=True, sequence=0
            )
            Room.objects.filter(pk=room.id).update(
                occupancy_status=RoomOccupancyStatus.OCCUPIED,
            )
            created_res += 1

        # --- Gelecek (yakın + uzun) ---
        for span_start, span_end, count in future_spans:
            for _ in range(count):
                nights = rnd.randint(1, 14)
                check_in = today + timedelta(days=rnd.randint(span_start, span_end))
                check_out = check_in + timedelta(days=nights)
                rt = rnd.choice(room_types)
                room = self._pick_room(occ, rt, check_in, check_out, rnd)
                if room is None:
                    room = self._pick_any_available_room(occ, check_in, check_out, rnd)
                if room:
                    occ.add(room.id, check_in, check_out)
                g = rnd.choice(guests)
                board = rnd.choice([BoardBasis.BB, BoardBasis.HB])
                adults = rnd.randint(1, 3)
                sub, tax, extras_raw, grand = self._compute_stay_charges(
                    rt, check_in, check_out, board, adults, rnd
                )
                if rnd.random() < 0.35:
                    dep = d0(grand * Decimal(str(rnd.uniform(0.1, 0.35))))
                else:
                    dep = Decimal("0")
                bal = d0(grand - dep)
                res = Reservation.objects.create(
                    hotel=hotel,
                    guest=g,
                    primary_guest_name=f"{g.first_name} {g.last_name}".strip(),
                    room=room,
                    room_type=rt,
                    channel=rnd.choice(channels),
                    check_in_date=check_in,
                    check_out_date=check_out,
                    nights=nights,
                    adults=adults,
                    status=ReservationStatus.UPCOMING,
                    board_basis=board,
                    total_amount=grand,
                    paid_amount=dep,
                    balance_amount=bal,
                    notes=f"Gelecek. {SEED_NOTE}",
                )
                self._write_folio_and_payments(
                    hotel,
                    res,
                    rt,
                    check_in,
                    check_out,
                    nights,
                    board,
                    sub,
                    tax,
                    extras_raw,
                    grand,
                    dep,
                    bal,
                    rnd,
                    closed=False,
                )
                ReservationOccupant.objects.create(
                    reservation=res, guest=g, is_primary=True, sequence=0
                )
                created_res += 1

        n_cash_ex = self._seed_operating_expenses(
            hotel, year_ago, today, rnd, day_prob=expense_day_prob
        )
        n_pay = Payment.objects.filter(
            reservation__hotel=hotel, reservation__notes__contains=SEED_NOTE
        ).count()
        n_cash_in = CashTransaction.objects.filter(
            hotel=hotel,
            description__contains=SEED_CASH_TAG,
            flow_type=CashFlowType.INCOME,
        ).count()
        return created_res, n_pay, n_cash_in, n_cash_ex

    def _room_line_label(self, rt: RoomType, nights: int, board: str) -> str:
        b = {"BB": "BB", "HB": "HB", "AI": "AI"}.get(board, board)
        return f"Konaklama — {rt.name} ({nights} gece, {b})"

    def _write_folio_and_payments(
        self,
        hotel: Hotel,
        res: Reservation,
        rt: RoomType,
        check_in: date,
        check_out: date,
        nights: int,
        board: str,
        sub_total: Decimal,
        tax: Decimal,
        extras_amount: Decimal,
        grand: Decimal,
        paid: Decimal,
        balance: Decimal,
        rnd: random.Random,
        *,
        closed: bool = True,
    ) -> int:
        """Folio satırları, Payment ve kasa geliri. Dönen: yeni ödeme adedi."""
        folio = Folio.objects.create(
            reservation=res,
            currency="TRY",
            opened_on=check_in,
            closed_on=check_out if closed else None,
        )
        room_and_board = d0(sub_total - extras_amount)
        FolioLine.objects.create(
            folio=folio,
            line_type=FolioLineType.ACCOMMODATION,
            description=self._room_line_label(rt, nights, board),
            amount=room_and_board,
            posted_date=check_in,
            source_module="seed",
        )
        if extras_amount > 0:
            FolioLine.objects.create(
                folio=folio,
                line_type=FolioLineType.EXTRA,
                description="Minibar / ek hizmet",
                amount=extras_amount,
                posted_date=check_in + timedelta(days=min(2, nights - 1)) if nights > 1 else check_in,
                source_module="seed",
            )
        if tax > 0:
            FolioLine.objects.create(
                folio=folio,
                line_type=FolioLineType.TAX,
                description="KDV (%10)",
                amount=tax,
                posted_date=check_in,
                source_module="seed",
            )

        pay_count = 0
        if paid <= 0:
            return pay_count

        pay_method_opts = [
            PaymentMethod.CREDIT_CARD,
            PaymentMethod.CASH,
            PaymentMethod.EFT,
        ]
        m_primary = rnd.choices(
            pay_method_opts,
            weights=[0.52, 0.35, 0.13],
            k=1,
        )[0]

        if closed and paid == grand and rnd.random() > 0.72:
            chunk1 = d0(paid * Decimal(str(rnd.uniform(0.35, 0.65))))
            chunk2 = d0(paid - chunk1)
            m2 = rnd.choice(pay_method_opts)
            chunks = [(chunk1, m_primary), (chunk2, m2)]
        else:
            chunks = [(paid, m_primary)]

        posted = check_in
        for amt, method in chunks:
            if amt <= 0:
                continue
            ctx = CashTransaction.objects.create(
                hotel=hotel,
                display_code=unique_cash_code(),
                flow_type=CashFlowType.INCOME,
                description=f"Tahsilat — {res.display_code or str(res.id)[:8]} {SEED_CASH_TAG}",
                amount=amt,
                method=method,
                tx_date=posted,
                reservation=res,
            )
            Payment.objects.create(
                reservation=res,
                amount=amt,
                method=method,
                cash_transaction=ctx,
            )
            FolioLine.objects.create(
                folio=folio,
                line_type=FolioLineType.PAYMENT,
                description=f"Ödeme ({method.label})",
                amount=-amt,
                posted_date=posted,
                source_module="seed",
            )
            pay_count += 1
            posted = check_out if closed else check_in + timedelta(days=min(1, max(nights - 1, 0)))

        return pay_count

    def _seed_operating_expenses(
        self,
        hotel: Hotel,
        year_start: date,
        today: date,
        rnd: random.Random,
        *,
        day_prob: float = 0.42,
    ) -> int:
        """Yıl boyunca gerçekçi gider kalemleri (kasa çıkışı)."""
        day_prob = max(0.0, min(1.0, float(day_prob)))
        templates = [
            ("Elektrik / su tüketimi", 8000, 28000),
            ("Temizlik malzemeleri", 1200, 6500),
            ("Çamaşırhane dış hizmet", 2500, 9000),
            ("Bakım-onarım / teknik", 1500, 12000),
            ("Yazılım / kanal abonelik", 4000, 15000),
            ("Pazarlama / reklam", 2000, 18000),
            ("Kırtasiye / ofis", 400, 2500),
            ("Bahçe / peyzaj", 800, 6000),
            ("Güvenlik hizmeti", 5000, 14000),
            ("Catering / personel yemeği", 3000, 11000),
        ]
        n = 0
        d = year_start
        while d <= today:
            if rnd.random() < day_prob:
                label, lo, hi = rnd.choice(templates)
                amt = d0(Decimal(str(rnd.randint(lo, hi))))
                CashTransaction.objects.create(
                    hotel=hotel,
                    display_code=unique_cash_code(),
                    flow_type=CashFlowType.EXPENSE,
                    description=f"{label} {SEED_CASH_TAG}",
                    amount=amt,
                    method=PaymentMethod.EFT,
                    tx_date=d,
                    reservation=None,
                )
                n += 1
            d += timedelta(days=1)
        return n

    def _sync_guest_totals(self, hotel: Hotel, guests: list[Guest]) -> None:
        gid_set = {g.id for g in guests}
        rows = (
            Reservation.objects.filter(
                hotel=hotel,
                guest_id__in=gid_set,
                status=ReservationStatus.CHECKED_OUT,
                notes__contains=SEED_NOTE,
            )
            .values("guest_id")
            .annotate(spent=Sum("paid_amount"), last_co=Max("check_out_date"))
        )
        by_guest = {r["guest_id"]: r for r in rows}
        for g in guests:
            info = by_guest.get(g.id)
            if not info:
                continue
            Guest.objects.filter(pk=g.pk).update(
                visit_count=Reservation.objects.filter(
                    hotel=hotel,
                    guest=g,
                    status=ReservationStatus.CHECKED_OUT,
                    notes__contains=SEED_NOTE,
                ).count(),
                total_spent=info["spent"] or Decimal("0"),
                last_visit_date=info["last_co"],
            )

    def _sync_room_occupancy_from_active_stays(self, hotel: Hotel) -> int:
        """
        Check-in + oda atanmış rezervasyonların hepsinde `Room.occupancy_status=occupied`
        (Room Rack / oda envanter / API tek kaynak).
        """
        room_ids = list(
            Reservation.objects.filter(
                hotel=hotel,
                status=ReservationStatus.CHECKED_IN,
                room_id__isnull=False,
            ).values_list("room_id", flat=True)
        )
        uniq = list({rid for rid in room_ids if rid})
        if not uniq:
            return 0
        return Room.objects.filter(hotel=hotel, pk__in=uniq).update(
            occupancy_status=RoomOccupancyStatus.OCCUPIED,
        )


class RoomOccupancyTracker:
    def __init__(self, rooms: list[Room]):
        self.all_rooms_list: list[Room] = list(rooms)
        self._by_type: dict[str, list[Room]] = defaultdict(list)
        for r in rooms:
            self._by_type[str(r.room_type_id)].append(r)
        self._intervals: dict[str, list[tuple[date, date]]] = defaultdict(list)

    def rooms_for_type(self, type_id) -> list[Room]:
        return self._by_type.get(str(type_id), [])

    def can_book(self, room_id, check_in: date, check_out: date) -> bool:
        for a, b in self._intervals[str(room_id)]:
            if not (check_out <= a or check_in >= b):
                return False
        return True

    def add(self, room_id, check_in: date, check_out: date) -> None:
        self._intervals[str(room_id)].append((check_in, check_out))

