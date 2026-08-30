"""DEMO otel için operasyonel modül tohumu.

PMS / İK / stok / muhasebe seed'inden sonra çalışır. Mevcut misafir, rezervasyon,
oda, personel ve stok kartlarına bağlanır; bölümler arasında aynı isimler görünür.

  py manage.py seed_ops_demo --hotel=DEMO
  py manage.py seed_ops_demo --hotel=DEMO --wipe
"""

from __future__ import annotations

import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hotelcrm.models import (
    AgencyContractRate,
    AgencyPromotion,
    BanquetEvent,
    ChannelManagerSettings,
    CommercialContract,
    CompetitorHotel,
    CrsSyncLog,
    EntertainmentActivity,
    EntertainmentShow,
    FolioLine,
    FoodWasteLog,
    Guest,
    GuestFeedbackEntry,
    GuestTransfer,
    GroupBooking,
    GroupBookingMember,
    Hotel,
    HotelSurveySmsSettings,
    IntegrationConnection,
    IntegrationEventLog,
    InventoryItem,
    ItAlarmWebhook,
    ItAlertLog,
    ItMetricSample,
    KbsGuestSubmission,
    KvkkConsent,
    LaundryOrder,
    LaundryOrderLine,
    LaundryPricelistItem,
    LostFoundItem,
    MarketingCampaign,
    MenuCategory,
    MenuItem,
    MinibarCharge,
    MinibarChargeLine,
    MinibarProduct,
    Notification,
    OperationalTask,
    Recipe,
    Reservation,
    RestaurantOrder,
    RestaurantOrderLine,
    Room,
    SalesLead,
    SpaAppointment,
    SpaService,
    StaffMember,
    SurveyInvitation,
    TourOffer,
    TravelAgency,
)
from hotelcrm.models.enums import (
    BanquetEventStatus,
    CommercialContractStatus,
    FolioLineType,
    GroupBookingStatus,
    LaundryOrderStatus,
    LostFoundStatus,
    LoyaltyTier,
    ReservationStatus,
    RestaurantOrderStatus,
    SalesLeadStage,
    SpaAppointmentStatus,
    TaskCategory,
    TaskStatus,
)
from hotelcrm.models.minibar_laundry_inv import InventoryUsageArea

SEED_TAG = "[seed-ops]"
PREFIX = "OPS"


def d2(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def code(kind: str, n: int) -> str:
    return f"{PREFIX}-{kind}-{n:03d}"


class Command(BaseCommand):
    help = "F&B, SPA, mini bar, çamaşırhane, grup, banket, acente ve diğer operasyon demo verisi."

    def add_arguments(self, parser):
        parser.add_argument("--hotel", default="DEMO")
        parser.add_argument("--wipe", action="store_true")

    def handle(self, *args, **options):
        hotel = Hotel.objects.filter(code__iexact=options["hotel"]).first()
        if not hotel:
            self.stderr.write(self.style.ERROR("Otel yok; önce seed_demo_hotel çalıştırın."))
            return

        if options["wipe"]:
            self._wipe(hotel)

        rnd = random.Random(20260831)
        today = timezone.localdate()
        now = timezone.now()

        rooms = list(Room.objects.filter(hotel=hotel).order_by("room_number"))
        guests = list(Guest.objects.filter(hotel=hotel).order_by("display_code"))
        inhouse = list(
            Reservation.objects.filter(
                hotel=hotel, status=ReservationStatus.CHECKED_IN
            ).select_related("guest", "room", "folio")
        )
        upcoming = list(
            Reservation.objects.filter(
                hotel=hotel, status=ReservationStatus.UPCOMING
            ).select_related("guest", "room")[:20]
        )
        checked_out = list(
            Reservation.objects.filter(
                hotel=hotel, status=ReservationStatus.CHECKED_OUT
            ).select_related("guest", "room")[:30]
        )
        staff = list(StaffMember.objects.filter(hotel=hotel, display_code__startswith="HR-DEMO-"))
        inventory = list(InventoryItem.objects.filter(hotel=hotel, is_archived=False))

        if not rooms or not guests:
            self.stderr.write(self.style.ERROR("Önce seed_pms_test_data çalıştırın (oda/misafir yok)."))
            return

        with transaction.atomic():
            self._loyalty(guests, rnd)
            self._competitors(hotel, now)
            self._channel_manager(hotel)
            agencies = self._agencies(hotel, today)
            self._sales_marketing(hotel, today, agencies)
            self._fnb_and_recipes(hotel, rnd, today, inhouse, rooms, inventory)
            self._spa(hotel, rnd, today, inhouse, staff)
            self._minibar(hotel, rnd, today, inhouse, inventory)
            self._laundry(hotel, rnd, today, inhouse)
            self._groups(hotel, today, upcoming, inhouse)
            self._banquet(hotel, today, agencies)
            self._lost_found(hotel, today, inhouse, rooms)
            self._tours_transfers(hotel, today, inhouse, upcoming)
            self._entertainment(hotel)
            self._kvkk_kbs_survey(hotel, today, now, guests, checked_out, inhouse)
            self._tasks_notif(hotel, rooms, staff, inhouse)
            self._integrations_it(hotel, now, rnd)
            self._crs_logs(hotel, guests, inhouse, upcoming)

        self.stdout.write(self.style.SUCCESS(f"Operasyon demo verisi yüklendi: {hotel.code}"))

    def _wipe(self, hotel: Hotel) -> None:
        FolioLine.objects.filter(
            folio__reservation__hotel=hotel, description__contains=SEED_TAG
        ).delete()
        RestaurantOrder.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-RO-").delete()
        MenuItem.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-MN-").delete()
        MenuCategory.objects.filter(hotel=hotel, name__startswith="Demo ").delete()
        SpaAppointment.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-SA-").delete()
        SpaService.objects.filter(hotel=hotel, name__startswith="Demo ").delete()
        MinibarCharge.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-MB-").delete()
        MinibarProduct.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-MP-").delete()
        LaundryOrder.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-LD-").delete()
        LaundryPricelistItem.objects.filter(hotel=hotel, name__startswith="Demo ").delete()
        GroupBooking.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-GR-").delete()
        BanquetEvent.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-BQ-").delete()
        LostFoundItem.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-LF-").delete()
        AgencyContractRate.objects.filter(agency__hotel=hotel, agency__display_code__startswith=f"{PREFIX}-AG-").delete()
        AgencyPromotion.objects.filter(agency__hotel=hotel, agency__display_code__startswith=f"{PREFIX}-AG-").delete()
        CommercialContract.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-CC-").delete()
        TravelAgency.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-AG-").delete()
        SalesLead.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-SL-").delete()
        MarketingCampaign.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-MC-").delete()
        TourOffer.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-TO-").delete()
        GuestTransfer.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-XF-").delete()
        Recipe.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-RC-").delete()
        FoodWasteLog.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-FW-").delete()
        EntertainmentActivity.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-EA-").delete()
        EntertainmentShow.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-ES-").delete()
        KvkkConsent.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-KV-").delete()
        SurveyInvitation.objects.filter(hotel=hotel, sms_message__contains=SEED_TAG).delete()
        GuestFeedbackEntry.objects.filter(hotel=hotel, comment__contains=SEED_TAG).delete()
        KbsGuestSubmission.objects.filter(hotel=hotel).delete()
        OperationalTask.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-TK-").delete()
        Notification.objects.filter(hotel=hotel, message__contains=SEED_TAG).delete()
        CrsSyncLog.objects.filter(action__contains=SEED_TAG).delete()
        ItAlertLog.objects.filter(hotel=hotel, message__contains=SEED_TAG).delete()
        ItAlarmWebhook.objects.filter(hotel=hotel, name__startswith="Demo ").delete()
        for integ in IntegrationConnection.objects.filter(hotel=hotel, display_code__startswith=f"{PREFIX}-IN-"):
            ItMetricSample.objects.filter(integration=integ).delete()
            IntegrationEventLog.objects.filter(integration=integ).delete()
            integ.delete()
        CompetitorHotel.objects.filter(hotel=hotel, notes__contains=SEED_TAG).delete()
        InventoryItem.objects.filter(hotel=hotel, sku__startswith="OPS-MB-").delete()
        self.stdout.write("Operasyon tohum kayıtları silindi.")

    def _post_folio(self, res: Reservation, desc: str, amount: Decimal, module: str, day: date) -> None:
        try:
            folio = res.folio
        except ObjectDoesNotExist:
            return
        FolioLine.objects.create(
            folio=folio,
            line_type=FolioLineType.EXTRA,
            description=f"{desc} {SEED_TAG}",
            amount=amount,
            posted_date=day,
            source_module=module,
        )
        res.total_amount = d2(res.total_amount + amount)
        res.balance_amount = d2(res.balance_amount + amount)
        res.save(update_fields=["total_amount", "balance_amount"])

    def _loyalty(self, guests: list[Guest], rnd: random.Random) -> None:
        tiers = (
            [LoyaltyTier.PLATINUM] * 2
            + [LoyaltyTier.GOLD] * 5
            + [LoyaltyTier.SILVER] * 8
        )
        for i, g in enumerate(guests[:15]):
            g.loyalty_tier = tiers[i] if i < len(tiers) else LoyaltyTier.NONE
            g.save(update_fields=["loyalty_tier"])

    def _competitors(self, hotel: Hotel, now) -> None:
        rows = (
            ("Four Seasons Bosphorus", "Çırağan Cad. No:28, Beşiktaş", "41.045210", "29.017640", "5.0", "9800"),
            ("Shangri-La Bosphorus", "Hayrettin İskelesi Sok. No:1", "41.041880", "29.017120", "5.0", "7200"),
            ("The Ritz-Carlton İstanbul", "Suzer Plaza, Askerocağı Cad.", "41.040110", "28.988540", "5.0", "8100"),
            ("Swissôtel The Bosphorus", "Bayıldım Cad. No:2", "41.042960", "29.011450", "5.0", "5400"),
            ("CVK Park Bosphorus", "Gümüşsuyu Mah. İnönü Cad.", "41.038720", "28.990210", "5.0", "3900"),
        )
        for name, addr, lat, lng, stars, price in rows:
            CompetitorHotel.objects.create(
                hotel=hotel,
                name=name,
                address=addr,
                latitude=Decimal(lat),
                longitude=Decimal(lng),
                star_rating=Decimal(stars),
                current_price=d2(price),
                currency="TRY",
                source="manual",
                last_observed_at=now,
                notes=f"Rakip fiyat karşılaştırması {SEED_TAG}",
            )

    def _channel_manager(self, hotel: Hotel) -> None:
        ChannelManagerSettings.objects.update_or_create(
            hotel=hotel,
            defaults={
                "rate_standard": d2(2400),
                "rate_deluxe": d2(3500),
                "rate_suite": d2(5500),
                "rate_family": d2(4800),
                "stop_sale_single": False,
                "stop_sale_double": False,
                "stop_sale_triple": False,
            },
        )

    def _agencies(self, hotel: Hotel, today: date) -> list[TravelAgency]:
        specs = (
            ("ETS Tur", "ETS Turizm A.Ş.", "12", "TR", "Ayşe Kara"),
            ("Booking.com B2B", "Booking.com B.V.", "15", "NL", "James Cole"),
            ("Setur", "Setur Servis Turistik A.Ş.", "10", "TR", "Mehmet Yıldız"),
        )
        out: list[TravelAgency] = []
        for i, (name, legal, comm, country, contact) in enumerate(specs, start=1):
            ag = TravelAgency.objects.create(
                hotel=hotel,
                display_code=code("AG", i),
                name=name,
                legal_name=legal,
                tax_office="Beşiktaş",
                tax_id=f"11122233{i:02d}",
                address="Levent, İstanbul",
                city="İstanbul",
                country=country,
                website=f"https://www.example-{i}.com",
                tursab_license_no=f"A-{1000 + i}",
                contact_name=contact,
                contact_title="Hesap yöneticisi",
                phone=f"0212 555 10{i:02d}",
                email=f"contracts{i}@agency-demo.test",
                billing_email=f"fatura{i}@agency-demo.test",
                commission_percent=d2(comm),
                payment_terms_days=30,
                payment_method="Havale",
                default_currency="TRY",
                credit_limit=d2(250000),
                allotment_rooms=12 + i * 4,
                contract_number=f"SOZ-2026-0{i}",
                contract_signed_date=today - timedelta(days=80),
                contract_start_date=date(today.year, 1, 1),
                contract_end_date=date(today.year, 12, 31),
                agency_status="active",
                internal_notes=SEED_TAG,
            )
            for j, (label, price, board) in enumerate(
                (("Standart", 2100, "BB"), ("Deluxe", 3100, "HB"), ("Süit", 4900, "AI")),
                start=1,
            ):
                AgencyContractRate.objects.create(
                    agency=ag,
                    valid_from=date(today.year, 1, 1),
                    valid_to=date(today.year, 12, 31),
                    room_type_label=label,
                    price=d2(price + i * 50),
                    currency="TRY",
                    board_basis=board,
                )
            AgencyPromotion.objects.create(
                agency=ag,
                name=f"{name} erken rezervasyon %12",
                description="60 gün öncesine kadar geçerli.",
                promo_status="active",
                valid_until=today + timedelta(days=90),
            )
            CommercialContract.objects.create(
                hotel=hotel,
                travel_agency=ag,
                display_code=code("CC", i),
                title=f"{name} 2026 allotment sözleşmesi",
                partner_name=legal,
                partner_tax_id=ag.tax_id,
                partner_contact_name=contact,
                partner_phone=ag.phone,
                partner_email=ag.email,
                contract_kind="allotment",
                start_date=ag.contract_start_date,
                end_date=ag.contract_end_date,
                pricing_terms=f"Komisyon %{comm}, 30 gün vade",
                status=CommercialContractStatus.ACTIVE,
                notes=SEED_TAG,
            )
            out.append(ag)
        return out

    def _sales_marketing(self, hotel: Hotel, today: date, agencies: list[TravelAgency]) -> None:
        leads = (
            ("Acıbadem Şirketler Grubu", "Kurumsal konaklama", SalesLeadStage.PROPOSAL, 186000, 55),
            ("Boğaziçi Üniversitesi Mezunlar", "Mezuniyet yemeği", SalesLeadStage.MEETING, 92000, 40),
            ("Lufthansa Crew", "Ekip bloğu", SalesLeadStage.WON, 240000, 90),
            ("Düğün - Yılmaz ailesi", "Düğün + oda bloğu", SalesLeadStage.NEW_LEAD, 175000, 20),
            ("TechSummit 2026", "Kongre", SalesLeadStage.LOST, 310000, 10),
        )
        for i, (account, note, stage, value, prob) in enumerate(leads, start=1):
            SalesLead.objects.create(
                hotel=hotel,
                display_code=code("SL", i),
                account_name=account,
                contact_name="Satış demo",
                phone=f"0532 400 10{i:02d}",
                estimated_value=d2(value),
                probability_percent=prob,
                stage=stage,
                created_date=today - timedelta(days=8 * i),
                notes=f"{note} {SEED_TAG}",
            )
        for i, (title, seg, status, n) in enumerate(
            (
                ("İstanbul'da 3 gece kaçış", "çiftler", "active", 18),
                ("Kurumsal kış kampanyası", "kurumsal", "active", 7),
                ("Erken rezervasyon yaz 2027", "aile", "draft", 0),
            ),
            start=1,
        ):
            MarketingCampaign.objects.create(
                hotel=hotel,
                display_code=code("MC", i),
                title=title,
                target_segment=seg,
                accent_color="#1d4ed8",
                campaign_status=status,
                reservation_count=n,
            )

    def _fnb_and_recipes(
        self,
        hotel: Hotel,
        rnd: random.Random,
        today: date,
        inhouse: list[Reservation],
        rooms: list[Room],
        inventory: list[InventoryItem],
    ) -> None:
        cats = []
        for name in ("Demo Kahvaltı", "Demo Ana yemek", "Demo İçecek", "Demo Tatlı"):
            cats.append(MenuCategory.objects.create(hotel=hotel, name=name))
        items_spec = (
            (0, "Serpme kahvaltı", 650),
            (0, "Omlet & sucuk", 280),
            (1, "Izgara levrek", 890),
            (1, "Dana antrikot", 980),
            (1, "Mantı", 420),
            (2, "Taze sıkılmış portakal", 160),
            (2, "Türk kahvesi", 90),
            (2, "Şişe su 0.75L", 45),
            (3, "Fırın sütlaç", 190),
            (3, "Çikolatalı sufle", 240),
        )
        menu_items = []
        for i, (ci, name, price) in enumerate(items_spec, start=1):
            menu_items.append(
                MenuItem.objects.create(
                    hotel=hotel,
                    category=cats[ci],
                    display_code=code("MN", i),
                    name=name,
                    unit_price=d2(price),
                )
            )
        recipes = (
            ("Levrek ızgara", 210, 890, "Levrek, zeytinyağı, limon, roka"),
            ("Antrikot", 340, 980, "Dana antrikot, tuz, biber, patates"),
            ("Sütlaç", 38, 190, "Süt, pirinç, şeker, tarçın"),
        )
        for i, (name, cost, price, ing) in enumerate(recipes, start=1):
            Recipe.objects.create(
                hotel=hotel,
                display_code=code("RC", i),
                name=name,
                cost_amount=d2(cost),
                menu_price=d2(price),
                ingredients_text=ing,
            )
        for i, (desc, reason, loss) in enumerate(
            (
                ("Açık büfe salata", "Servis fazlası", 420),
                ("Balık stok", "SKT geçti", 680),
                ("Ekmek", "Bayatlama", 95),
            ),
            start=1,
        ):
            FoodWasteLog.objects.create(
                hotel=hotel,
                display_code=code("FW", i),
                item_description=desc,
                reason=reason,
                loss_amount=d2(loss),
                waste_date=today - timedelta(days=i),
            )

        rest_inv = [it for it in inventory if it.usage_area == InventoryUsageArea.RESTAURANT][:4]
        targets = inhouse[:4] if inhouse else []
        for i in range(8):
            res = targets[i] if i < len(targets) else None
            room = res.room if res and res.room_id else rnd.choice(rooms)
            picked = rnd.sample(menu_items, k=3)
            lines = []
            total = Decimal("0")
            for mi in picked:
                qty = rnd.randint(1, 2)
                lt = d2(mi.unit_price * qty)
                total += lt
                lines.append((mi, qty, lt))
            order = RestaurantOrder.objects.create(
                hotel=hotel,
                display_code=code("RO", i + 1),
                table_label="" if res else f"Masa {4 + i}",
                room=room,
                reservation=res,
                status=rnd.choice(
                    [
                        RestaurantOrderStatus.COMPLETED,
                        RestaurantOrderStatus.READY,
                        RestaurantOrderStatus.PREPARING,
                    ]
                ),
                total_amount=total,
                order_date=today - timedelta(days=0 if res else rnd.randint(0, 4)),
                order_time=time(rnd.randint(8, 21), rnd.choice((0, 15, 30, 45))),
            )
            for mi, qty, lt in lines:
                inv = rest_inv[i % len(rest_inv)] if rest_inv and i % 2 == 0 else None
                RestaurantOrderLine.objects.create(
                    order=order,
                    menu_item=mi,
                    inventory_item=inv,
                    item_name=mi.name,
                    quantity=qty,
                    unit_price=mi.unit_price,
                    line_total=lt,
                )
            if res and order.status == RestaurantOrderStatus.COMPLETED:
                self._post_folio(res, f"Restoran {order.display_code}", total, "fnb", order.order_date)

    def _spa(
        self,
        hotel: Hotel,
        rnd: random.Random,
        today: date,
        inhouse: list[Reservation],
        staff: list[StaffMember],
    ) -> None:
        therapists = [s.full_name for s in staff if s.department and "SPA" in (s.department.name or "")]
        if not therapists:
            therapists = ["Elif Demir", "Can Yıldız"]
        services = []
        for i, (name, price) in enumerate(
            (("Klasik masaj 50 dk", 2200), ("Cilt bakımı", 1800), ("Hamam ritüeli", 1600), ("Çift masaj", 3900)),
            start=1,
        ):
            services.append(
                SpaService.objects.create(
                    hotel=hotel,
                    name=f"Demo {name}",
                    default_price=d2(price),
                    default_therapist=therapists[i % len(therapists)],
                )
            )
        for i in range(6):
            res = inhouse[i % len(inhouse)] if inhouse else None
            svc = services[i % len(services)]
            st = (
                SpaAppointmentStatus.COMPLETED
                if i < 3
                else SpaAppointmentStatus.SCHEDULED
            )
            day = today if i >= 3 else today - timedelta(days=1)
            SpaAppointment.objects.create(
                hotel=hotel,
                display_code=code("SA", i + 1),
                guest_name=res.primary_guest_name if res else "Walk-in SPA",
                room=res.room if res else None,
                reservation=res,
                spa_service=svc,
                service_name_snapshot=svc.name,
                therapist_name=svc.default_therapist,
                appointment_date=day,
                appointment_time=time(10 + i, 0),
                status=st,
                price=svc.default_price,
            )
            if res and st == SpaAppointmentStatus.COMPLETED:
                self._post_folio(res, svc.name, svc.default_price, "spa", day)

    def _minibar(
        self,
        hotel: Hotel,
        rnd: random.Random,
        today: date,
        inhouse: list[Reservation],
        inventory: list[InventoryItem],
    ) -> None:
        catalog = (
            ("Kola 330ml", "İçecek", 95),
            ("Su 330ml", "İçecek", 45),
            ("Fıstık 50g", "Atıştırmalık", 120),
            ("Çikolata", "Atıştırmalık", 140),
            ("Bira 330ml", "İçecek", 180),
            ("Şarap 187ml", "İçecek", 320),
        )
        products = []
        mb_items = []
        for i, (name, cat, price) in enumerate(catalog, start=1):
            products.append(
                MinibarProduct.objects.create(
                    hotel=hotel,
                    display_code=code("MP", i),
                    name=name,
                    category=cat,
                    unit_price=d2(price),
                )
            )
            mb_items.append(
                InventoryItem.objects.create(
                    hotel=hotel,
                    name=name,
                    category=cat,
                    warehouse="HK",
                    usage_area=InventoryUsageArea.MINIBAR,
                    sale_price=d2(price),
                    unit="adet",
                    quantity_on_hand=d2(80 + i * 10),
                    min_quantity=d2(20),
                    max_quantity=d2(200),
                    unit_cost=d2(price * Decimal("0.35")),
                    sku=f"OPS-MB-{i:03d}",
                    notes=SEED_TAG,
                )
            )
        for i, res in enumerate(inhouse[:5], start=1):
            if not res.room_id:
                continue
            picks = rnd.sample(list(zip(products, mb_items, strict=True)), k=2)
            total = Decimal("0")
            ch = MinibarCharge.objects.create(
                hotel=hotel,
                display_code=code("MB", i),
                room=res.room,
                reservation=res,
                charge_date=today,
                total_amount=0,
                billed_to_folio=True,
            )
            for prod, inv in picks:
                qty = rnd.randint(1, 2)
                MinibarChargeLine.objects.create(
                    charge=ch,
                    product=prod,
                    inventory_item=inv,
                    name_snapshot=prod.name,
                    quantity=qty,
                    unit_price=prod.unit_price,
                )
                total += prod.unit_price * qty
            ch.total_amount = d2(total)
            ch.save(update_fields=["total_amount"])
            self._post_folio(res, f"Mini bar {ch.display_code}", ch.total_amount, "minibar", today)

    def _laundry(self, hotel: Hotel, rnd: random.Random, today: date, inhouse: list[Reservation]) -> None:
        prices = []
        for name, price in (
            ("Gömlek", 90),
            ("Pantolon", 110),
            ("Elbise", 180),
            ("Takım elbise", 320),
            ("Havludan fazla (misafir)", 40),
        ):
            prices.append(
                LaundryPricelistItem.objects.create(
                    hotel=hotel, name=f"Demo {name}", unit_price=d2(price)
                )
            )
        for i, res in enumerate(inhouse[:4], start=1):
            if not res.room_id:
                continue
            picks = rnd.sample(prices, k=2)
            total = Decimal("0")
            order = LaundryOrder.objects.create(
                hotel=hotel,
                display_code=code("LD", i),
                room=res.room,
                reservation=res,
                guest_name=res.primary_guest_name,
                order_date=today,
                ordered_time=time(9, 30),
                status=LaundryOrderStatus.READY if i < 3 else LaundryOrderStatus.WASHING,
                total_amount=0,
            )
            for pl in picks:
                qty = 1
                LaundryOrderLine.objects.create(
                    laundry_order=order,
                    pricelist_item=pl,
                    name_snapshot=pl.name,
                    quantity=qty,
                    unit_price=pl.unit_price,
                )
                total += pl.unit_price
            order.total_amount = d2(total)
            order.save(update_fields=["total_amount"])
            if order.status == LaundryOrderStatus.READY:
                self._post_folio(res, f"Çamaşırhane {order.display_code}", order.total_amount, "laundry", today)

    def _groups(
        self,
        hotel: Hotel,
        today: date,
        upcoming: list[Reservation],
        inhouse: list[Reservation],
    ) -> None:
        blocks = (
            (
                "Lufthansa ekip bloğu",
                GroupBookingStatus.ACTIVE,
                today - timedelta(days=1),
                today + timedelta(days=3),
                inhouse[:3],
            ),
            (
                "Setur İstanbul turu",
                GroupBookingStatus.CONFIRMED,
                today + timedelta(days=12),
                today + timedelta(days=16),
                upcoming[:4],
            ),
        )
        for i, (name, status, cin, cout, members) in enumerate(blocks, start=1):
            pax = max(len(members) * 2, 4)
            total = d2(sum((m.total_amount for m in members), Decimal("0")) or 48000)
            paid = d2(total * Decimal("0.4"))
            gb = GroupBooking.objects.create(
                hotel=hotel,
                display_code=code("GR", i),
                name=name,
                leader_name=members[0].primary_guest_name if members else "Grup lideri",
                phone="0532 111 2233",
                pax_total=pax,
                rooms_blocked=max(len(members), 2),
                check_in=cin,
                check_out=cout,
                status=status,
                total_amount=total,
                paid_amount=paid,
                board_basis="HB",
                notes=SEED_TAG,
            )
            for seq, res in enumerate(members):
                GroupBookingMember.objects.create(
                    group_booking=gb,
                    full_name=res.primary_guest_name,
                    phone=res.guest.phone if res.guest else "",
                    room=res.room,
                    reservation=res,
                    sequence=seq,
                    is_leader=seq == 0,
                )

    def _banquet(self, hotel: Hotel, today: date, agencies: list[TravelAgency]) -> None:
        events = (
            ("Yılmaz – Demir düğünü", "düğün", "Boğaz Salonu", today + timedelta(days=21), 180, 245000),
            ("Acıbadem Q3 toplantısı", "toplantı", "Lale Oda", today + timedelta(days=5), 40, 28000),
            ("TechSummit kokteyl", "kokteyl", "Teras", today - timedelta(days=4), 90, 54000),
        )
        statuses = (
            BanquetEventStatus.APPROVED,
            BanquetEventStatus.PENDING,
            BanquetEventStatus.COMPLETED,
        )
        for i, (name, typ, hall, day, pax, amt) in enumerate(events, start=1):
            BanquetEvent.objects.create(
                hotel=hotel,
                display_code=code("BQ", i),
                name=name,
                event_type=typ,
                hall_name=hall,
                event_date=day,
                start_time=time(19, 0) if typ != "toplantı" else time(9, 30),
                pax=pax,
                status=statuses[i - 1],
                total_amount=d2(amt),
                paid_amount=d2(amt * (0.5 if i < 3 else 1)),
                contact_name=agencies[0].contact_name if agencies else "Etkinlik",
                phone="0212 555 8800",
                email="events@demo-hotel.test",
                notes=SEED_TAG,
            )

    def _lost_found(
        self,
        hotel: Hotel,
        today: date,
        inhouse: list[Reservation],
        rooms: list[Room],
    ) -> None:
        items = (
            ("Altın kolye", "takı", "waiting"),
            ("iPhone şarj aleti", "elektronik", "waiting"),
            ("Çocuk oyuncağı", "diğer", "returned"),
            ("Güneş gözlüğü", "aksesuar", "waiting"),
            ("Pasaport kılıfı", "belge", "returned"),
        )
        for i, (title, cat, st) in enumerate(items, start=1):
            room = inhouse[i % len(inhouse)].room if inhouse and inhouse[i % len(inhouse)].room else rooms[0]
            returned = ""
            if st == LostFoundStatus.RETURNED and inhouse:
                returned = inhouse[0].primary_guest_name
            LostFoundItem.objects.create(
                hotel=hotel,
                display_code=code("LF", i),
                title=title,
                category=cat,
                location_found=f"Oda {room.room_number}" if room else "Lobi",
                description=SEED_TAG,
                found_date=today - timedelta(days=i),
                status=st,
                returned_to_guest_name=returned,
            )

    def _tours_transfers(
        self,
        hotel: Hotel,
        today: date,
        inhouse: list[Reservation],
        upcoming: list[Reservation],
    ) -> None:
        tours = (
            ("Boğaz turu", "şehir", 1450),
            ("Prens Adaları", "günübire", 2100),
            ("Kapalıçarşı yürüyüşü", "şehir", 650),
        )
        for i, (name, kind, price) in enumerate(tours, start=1):
            res = inhouse[i % len(inhouse)] if inhouse else None
            TourOffer.objects.create(
                hotel=hotel,
                display_code=code("TO", i),
                name=name,
                tour_kind=kind,
                guest_name=res.primary_guest_name if res else "Misafir",
                tour_date=today + timedelta(days=i),
                pax=2,
                status="confirmed",
                price=d2(price),
            )
        pool = (inhouse + upcoming)[:4]
        for i, res in enumerate(pool, start=1):
            GuestTransfer.objects.create(
                hotel=hotel,
                display_code=code("XF", i),
                direction="arrival" if i % 2 else "departure",
                guest_name=res.primary_guest_name,
                location_label="IST Havalimanı",
                flight_code=f"TK{100 + i}",
                transfer_date=res.check_in_date if i % 2 else res.check_out_date,
                transfer_time=time(14, 30) if i % 2 else time(11, 0),
                vehicle_label="Mercedes Vito",
                status="planned",
            )

    def _entertainment(self, hotel: Hotel) -> None:
        acts = (
            ("Sabah yoga", "07:30", "08:15", "Bahçe", "spor", "her gün"),
            ("Çocuk kulübü", "10:00", "12:00", "Kids Club", "çocuk", "her gün"),
            ("Canlı müzik", "20:30", "22:30", "Lobi bar", "müzik", "cuma-ctesi"),
            ("Su jimnastiği", "11:00", "11:40", "Havuz", "spor", "hafta içi"),
        )
        for i, (name, st, en, loc, cat, day) in enumerate(acts, start=1):
            sh, sm = st.split(":")
            eh, em = en.split(":")
            EntertainmentActivity.objects.create(
                hotel=hotel,
                display_code=code("EA", i),
                name=name,
                start_time=time(int(sh), int(sm)),
                end_time=time(int(eh), int(em)),
                location_name=loc,
                category=cat,
                day_label=day,
                status="active",
                participant_count=12 + i * 3,
            )
        for i, (title, when, hh, icon) in enumerate(
            (("Türk gecesi", "Cuma", 21, "🎵"), ("Sihirbazlık", "Cumartesi", 20, "🎩"), ("Akustik", "Pazar", 19, "🎸")),
            start=1,
        ):
            EntertainmentShow.objects.create(
                hotel=hotel,
                display_code=code("ES", i),
                title=title,
                show_date_label=when,
                start_time=time(hh, 0),
                icon=icon,
            )

    def _kvkk_kbs_survey(
        self,
        hotel: Hotel,
        today: date,
        now,
        guests: list[Guest],
        checked_out: list[Reservation],
        inhouse: list[Reservation],
    ) -> None:
        HotelSurveySmsSettings.objects.update_or_create(
            hotel=hotel,
            defaults={
                "provider": HotelSurveySmsSettings.Provider.MOCK,
                "sender_id": "DEMOHOTEL",
                "is_enabled": True,
            },
        )
        for i, g in enumerate(guests[:8], start=1):
            KvkkConsent.objects.create(
                hotel=hotel,
                display_code=code("KV", i),
                guest_name=f"{g.first_name} {g.last_name}".strip(),
                consent_type="aydınlatma" if i % 2 else "pazarlama",
                consent_status="granted",
                record_date=today - timedelta(days=i),
                recorded_by="Resepsiyon",
                note=SEED_TAG,
            )
        for i, res in enumerate((inhouse + checked_out)[:6], start=1):
            g = res.guest
            KbsGuestSubmission.objects.create(
                hotel=hotel,
                reservation=res,
                sent_at=now - timedelta(hours=i),
                national_id=g.national_id or f"SEED{i:07d}",
                passport_no=g.passport_no or "",
                nationality=g.nationality or "TR",
            )
        for i, res in enumerate(checked_out[:8], start=1):
            g = res.guest
            completed = i <= 5
            answers = {}
            score = None
            if completed:
                answers = {
                    "overall": 4 if i % 3 else 5,
                    "cleanliness": 5,
                    "staff": 4,
                    "food": 4,
                    "recommend": True,
                    "comment": "Harika bir konaklama.",
                }
                score = d2((answers["overall"] + answers["cleanliness"] + answers["staff"] + answers["food"]) / 4)
            SurveyInvitation.objects.create(
                hotel=hotel,
                guest=g,
                guest_name=res.primary_guest_name,
                phone=(g.phone if g and g.phone else "05320000000")[:32],
                room_number=res.room.room_number if res.room else "",
                status=(
                    SurveyInvitation.Status.COMPLETED
                    if completed
                    else SurveyInvitation.Status.SENT
                ),
                sms_message=f"Anket daveti {SEED_TAG}",
                answers=answers,
                overall_score=score,
                sent_at=now - timedelta(days=2),
                completed_at=now - timedelta(days=1) if completed else None,
            )
            GuestFeedbackEntry.objects.create(
                hotel=hotel,
                guest_name=res.primary_guest_name,
                room_number=res.room.room_number if res.room else "",
                score=int(score or 4),
                comment=f"Ön büro ve oda çok iyi. {SEED_TAG}",
                category="genel",
            )

    def _tasks_notif(
        self,
        hotel: Hotel,
        rooms: list[Room],
        staff: list[StaffMember],
        inhouse: list[Reservation],
    ) -> None:
        hk = [s for s in staff if s.department and "Kat" in (s.department.name or "")]
        tech = [s for s in staff if s.department and "Teknik" in (s.department.name or "")]
        dirty = [r for r in rooms if r.clean_status == "dirty"] or rooms[:4]
        jobs = (
            (TaskCategory.HOUSEKEEPING, "Çıkış temizliği", TaskStatus.IN_PROGRESS, hk),
            (TaskCategory.HOUSEKEEPING, "Turn-down servisi", TaskStatus.PENDING, hk),
            (TaskCategory.TECHNICAL, "Klima arıza bildirimi", TaskStatus.IN_PROGRESS, tech),
            (TaskCategory.TECHNICAL, "Minibar soğutmuyor", TaskStatus.PENDING, tech),
            (TaskCategory.HOUSEKEEPING, "Ekstra havlu talebi", TaskStatus.DONE, hk),
        )
        for i, (cat, title, st, pool) in enumerate(jobs, start=1):
            room = inhouse[(i - 1) % len(inhouse)].room if inhouse and inhouse[(i - 1) % len(inhouse)].room else dirty[i % len(dirty)]
            OperationalTask.objects.create(
                hotel=hotel,
                display_code=code("TK", i),
                category=cat,
                room=room,
                title=title,
                priority="high" if i in (3, 4) else "normal",
                status=st,
                assignee=pool[0] if pool else (staff[0] if staff else None),
                note=SEED_TAG,
            )
        for msg in (
            "Oda 205 klima arızası teknik servise iletildi.",
            "Lufthansa grubu yarın çıkış yapacak — ön büro hazırlığı.",
            "Mini bar stok: kola kritik seviyenin altında.",
        ):
            Notification.objects.create(hotel=hotel, notif_type="ops", message=f"{msg} {SEED_TAG}")

    def _integrations_it(self, hotel: Hotel, now, rnd: random.Random) -> None:
        specs = (
            ("Channel Manager", "channel", "connected"),
            ("e-Fatura", "einvoice", "connected"),
            ("PMS host ajanı", "it-host", "connected"),
            ("SMS Netgsm", "sms", "idle"),
        )
        created = []
        for i, (name, kind, st) in enumerate(specs, start=1):
            integ = IntegrationConnection.objects.create(
                hotel=hotel,
                display_code=code("IN", i),
                name=name,
                integration_kind=kind,
                connection_status=st,
                api_key_ref=f"demo-key-{i}",
                last_sync_label="2 dk önce" if st == "connected" else "—",
                monitor_enabled=(kind == "it-host"),
                host_hostname="demo-front-desk-01" if kind == "it-host" else "",
                last_heartbeat_at=now if kind == "it-host" else None,
                cpu_percent=d2(28) if kind == "it-host" else None,
                memory_percent=d2(54) if kind == "it-host" else None,
                disk_percent=d2(41) if kind == "it-host" else None,
            )
            created.append(integ)
            IntegrationEventLog.objects.create(
                integration=integ,
                service_code=kind,
                event_type="sync",
                outcome="ok" if st == "connected" else "skip",
                meta=SEED_TAG,
            )
        host = next((x for x in created if x.integration_kind == "it-host"), None)
        if host:
            for m in range(8):
                ItMetricSample.objects.create(
                    integration=host,
                    cpu_percent=d2(20 + rnd.randint(0, 25)),
                    memory_percent=d2(45 + rnd.randint(0, 20)),
                    disk_percent=d2(40),
                    network_mbps_in=d2("1.2"),
                    network_mbps_out=d2("0.4"),
                )
            hook = ItAlarmWebhook.objects.create(
                hotel=hotel,
                name="Demo Slack IT alarm",
                target_url="https://example.com/hooks/it-demo",
                is_enabled=True,
            )
            ItAlertLog.objects.create(
                hotel=hotel,
                integration=host,
                webhook=hook,
                alert_kind="cpu",
                severity="warning",
                message=f"CPU %82 eşiği aşıldı {SEED_TAG}",
                webhook_status="sent",
            )

    def _crs_logs(
        self,
        hotel: Hotel,
        guests: list[Guest],
        inhouse: list[Reservation],
        upcoming: list[Reservation],
    ) -> None:
        samples = (inhouse + upcoming)[:5]
        for res in samples:
            CrsSyncLog.objects.create(
                action=f"Rezervasyon senkron {SEED_TAG}",
                from_label="Booking.com",
                to_label=hotel.code,
                guest_or_ref=res.display_code or res.primary_guest_name,
                outcome="ok",
            )
        if guests:
            CrsSyncLog.objects.create(
                action=f"Allotment güncellemesi {SEED_TAG}",
                from_label=hotel.code,
                to_label="Channel Manager",
                guest_or_ref="SEED_STD",
                outcome="ok",
            )
