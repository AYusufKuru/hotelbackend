"""Otel kaydını silmeden otel kapsamındaki operasyonel veriyi temizler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from django.apps import apps
from django.db import transaction
from django.db.models import Model, QuerySet

from hotelcrm.models import Hotel

Scope = str

SCOPE_RESERVATIONS = "reservations"
SCOPE_GUESTS = "guests"
SCOPE_ROOMS = "rooms"
SCOPE_ACCOUNTING = "accounting"
SCOPE_STAFF = "staff"
SCOPE_INVENTORY = "inventory"
SCOPE_OPERATIONS = "operations"
SCOPE_ALL = "all"

ALL_SCOPES = frozenset(
    {
        SCOPE_RESERVATIONS,
        SCOPE_GUESTS,
        SCOPE_ROOMS,
        SCOPE_ACCOUNTING,
        SCOPE_STAFF,
        SCOPE_INVENTORY,
        SCOPE_OPERATIONS,
        SCOPE_ALL,
    }
)


@dataclass
class PurgeResult:
    hotel_code: str
    scopes: list[str]
    dry_run: bool
    deleted: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.deleted.values())


def _count(qs: QuerySet) -> int:
    return qs.count()


def _delete_qs(qs: QuerySet, *, dry_run: bool) -> int:
    n = _count(qs)
    if n and not dry_run:
        qs.delete()
    return n


def _model(label: str) -> type[Model]:
    return apps.get_model(label)


def _hotel_qs(model_label: str, hotel: Hotel) -> QuerySet:
    model = _model(model_label)
    return model.objects.filter(hotel=hotel)


def _res_qs(hotel: Hotel) -> QuerySet:
    Reservation = _model("hotelcrm.Reservation")
    return Reservation.objects.filter(hotel=hotel)


def _purge_reservations(hotel: Hotel, *, dry_run: bool, deleted: dict[str, int]) -> None:
    res_qs = _res_qs(hotel)
    res_ids = list(res_qs.values_list("id", flat=True))
    if not res_ids:
        return

    Payment = _model("hotelcrm.Payment")
    deleted["payment"] = _delete_qs(Payment.objects.filter(reservation_id__in=res_ids), dry_run=dry_run)

    CashTransaction = _model("hotelcrm.CashTransaction")
    deleted["cash_transaction_unlink"] = _count(
        CashTransaction.objects.filter(hotel=hotel, reservation_id__in=res_ids),
    )
    if deleted["cash_transaction_unlink"] and not dry_run:
        CashTransaction.objects.filter(hotel=hotel, reservation_id__in=res_ids).update(reservation=None)

    KbsGuestSubmission = _model("hotelcrm.KbsGuestSubmission")
    deleted["kbs_submission"] = _delete_qs(
        KbsGuestSubmission.objects.filter(hotel=hotel, reservation_id__in=res_ids),
        dry_run=dry_run,
    )

    for label, fk in (
        ("hotelcrm.MinibarCharge", "reservation_id__in"),
        ("hotelcrm.LaundryOrder", "reservation_id__in"),
        ("hotelcrm.RestaurantOrder", "reservation_id__in"),
        ("hotelcrm.SpaAppointment", "reservation_id__in"),
    ):
        model = _model(label)
        deleted[label.split(".")[-1].lower() + "_unlink"] = _count(
            model.objects.filter(hotel=hotel, reservation_id__in=res_ids),
        )
        if deleted[label.split(".")[-1].lower() + "_unlink"] and not dry_run:
            model.objects.filter(hotel=hotel, reservation_id__in=res_ids).update(reservation=None)

    deleted["reservation"] = _delete_qs(res_qs, dry_run=dry_run)


def _purge_guests(hotel: Hotel, *, dry_run: bool, deleted: dict[str, int]) -> None:
    deleted["guest"] = _delete_qs(_hotel_qs("hotelcrm.Guest", hotel), dry_run=dry_run)


def _purge_rooms(hotel: Hotel, *, dry_run: bool, deleted: dict[str, int]) -> None:
    deleted["room"] = _delete_qs(_hotel_qs("hotelcrm.Room", hotel), dry_run=dry_run)
    deleted["room_type"] = _delete_qs(_hotel_qs("hotelcrm.RoomType", hotel), dry_run=dry_run)
    deleted["channel"] = _delete_qs(_hotel_qs("hotelcrm.Channel", hotel), dry_run=dry_run)


def _purge_accounting(hotel: Hotel, *, dry_run: bool, deleted: dict[str, int]) -> None:
    for label in (
        "hotelcrm.JournalEntry",
        "hotelcrm.OperationalInvoice",
        "hotelcrm.PurchaseOrder",
        "hotelcrm.FixedAsset",
        "hotelcrm.BusinessPartner",
        "hotelcrm.DepartmentBudget",
        "hotelcrm.GLAccount",
        "hotelcrm.CommercialContract",
    ):
        deleted[label.split(".")[-1].lower()] = _delete_qs(
            _hotel_qs(label, hotel),
            dry_run=dry_run,
        )

    TravelAgency = _model("hotelcrm.TravelAgency")
    agency_ids = list(TravelAgency.objects.filter(hotel=hotel).values_list("id", flat=True))
    if agency_ids:
        AgencyPromotion = _model("hotelcrm.AgencyPromotion")
        AgencyContractRate = _model("hotelcrm.AgencyContractRate")
        deleted["agency_promotion"] = _delete_qs(
            AgencyPromotion.objects.filter(agency_id__in=agency_ids),
            dry_run=dry_run,
        )
        deleted["agency_contract_rate"] = _delete_qs(
            AgencyContractRate.objects.filter(agency_id__in=agency_ids),
            dry_run=dry_run,
        )
    deleted["travel_agency"] = _delete_qs(_hotel_qs("hotelcrm.TravelAgency", hotel), dry_run=dry_run)


def _purge_staff(hotel: Hotel, *, dry_run: bool, deleted: dict[str, int]) -> None:
    deleted["staff_absence_report"] = _delete_qs(
        _hotel_qs("hotelcrm.StaffAbsenceReport", hotel),
        dry_run=dry_run,
    )
    deleted["staff_member"] = _delete_qs(_hotel_qs("hotelcrm.StaffMember", hotel), dry_run=dry_run)
    deleted["department"] = _delete_qs(_hotel_qs("hotelcrm.Department", hotel), dry_run=dry_run)
    deleted["hotel_recruitment"] = _delete_qs(
        _hotel_qs("hotelcrm.HotelRecruitment", hotel),
        dry_run=dry_run,
    )


def _purge_inventory(hotel: Hotel, *, dry_run: bool, deleted: dict[str, int]) -> None:
    StockCountLine = _model("hotelcrm.StockCountLine")
    StockCountSession = _model("hotelcrm.StockCountSession")
    session_ids = list(StockCountSession.objects.filter(hotel=hotel).values_list("id", flat=True))
    if session_ids:
        deleted["stock_count_line"] = _delete_qs(
            StockCountLine.objects.filter(session_id__in=session_ids),
            dry_run=dry_run,
        )
    deleted["stock_count_session"] = _delete_qs(
        StockCountSession.objects.filter(hotel=hotel),
        dry_run=dry_run,
    )
    deleted["stock_movement"] = _delete_qs(
        _hotel_qs("hotelcrm.StockMovement", hotel),
        dry_run=dry_run,
    )
    deleted["inventory_stock_lot"] = _delete_qs(
        _hotel_qs("hotelcrm.InventoryStockLot", hotel),
        dry_run=dry_run,
    )
    deleted["inventory_item"] = _delete_qs(
        _hotel_qs("hotelcrm.InventoryItem", hotel),
        dry_run=dry_run,
    )


def _purge_operations(hotel: Hotel, *, dry_run: bool, deleted: dict[str, int]) -> None:
    for label in (
        "hotelcrm.CashTransaction",
        "hotelcrm.OperationalTask",
        "hotelcrm.Notification",
        "hotelcrm.RestaurantOrder",
        "hotelcrm.MinibarCharge",
        "hotelcrm.MinibarProduct",
        "hotelcrm.LaundryOrder",
        "hotelcrm.LaundryPricelistItem",
        "hotelcrm.SpaAppointment",
        "hotelcrm.SpaService",
        "hotelcrm.MenuItem",
        "hotelcrm.MenuCategory",
        "hotelcrm.GroupBooking",
        "hotelcrm.BanquetEvent",
        "hotelcrm.LostFoundItem",
        "hotelcrm.SalesLead",
        "hotelcrm.MarketingCampaign",
        "hotelcrm.TourOffer",
        "hotelcrm.GuestTransfer",
        "hotelcrm.Recipe",
        "hotelcrm.FoodWasteLog",
        "hotelcrm.EntertainmentActivity",
        "hotelcrm.EntertainmentShow",
        "hotelcrm.KvkkConsent",
        "hotelcrm.GuestFeedbackEntry",
        "hotelcrm.SurveyInvitation",
        "hotelcrm.ItAlertLog",
        "hotelcrm.ItAlarmWebhook",
        "hotelcrm.CompetitorHotel",
        "hotelcrm.AuditLog",
    ):
        deleted[label.split(".")[-1].lower()] = _delete_qs(
            _hotel_qs(label, hotel),
            dry_run=dry_run,
        )

    IntegrationConnection = _model("hotelcrm.IntegrationConnection")
    conn_ids = list(IntegrationConnection.objects.filter(hotel=hotel).values_list("id", flat=True))
    if conn_ids:
        ItMetricSample = _model("hotelcrm.ItMetricSample")
        IntegrationEventLog = _model("hotelcrm.IntegrationEventLog")
        deleted["it_metric_sample"] = _delete_qs(
            ItMetricSample.objects.filter(integration_id__in=conn_ids),
            dry_run=dry_run,
        )
        deleted["integration_event_log"] = _delete_qs(
            IntegrationEventLog.objects.filter(integration_id__in=conn_ids),
            dry_run=dry_run,
        )
    deleted["integration_connection"] = _delete_qs(
        IntegrationConnection.objects.filter(hotel=hotel),
        dry_run=dry_run,
    )

    for label in ("hotelcrm.ChannelManagerSettings", "hotelcrm.HotelSurveySmsSettings"):
        deleted[label.split(".")[-1].lower()] = _delete_qs(
            _hotel_qs(label, hotel),
            dry_run=dry_run,
        )


def _reset_sequences(hotel: Hotel, *, dry_run: bool) -> None:
    if dry_run:
        return
    hotel.guest_sequence = 0
    hotel.reservation_sequence = 0
    hotel.save(update_fields=["guest_sequence", "reservation_sequence"])


def purge_hotel_data(
    hotel: Hotel,
    *,
    scopes: list[Scope] | None = None,
    dry_run: bool = False,
    reset_sequences: bool = True,
) -> PurgeResult:
    """Otel kaydını koruyarak seçilen kapsamlardaki veriyi siler."""
    selected = scopes or [SCOPE_ALL]
    if SCOPE_ALL in selected:
        selected = [
            SCOPE_RESERVATIONS,
            SCOPE_OPERATIONS,
            SCOPE_INVENTORY,
            SCOPE_ACCOUNTING,
            SCOPE_STAFF,
            SCOPE_GUESTS,
            SCOPE_ROOMS,
        ]

    unknown = set(selected) - ALL_SCOPES
    if unknown:
        raise ValueError(f"Bilinmeyen scope: {', '.join(sorted(unknown))}")

    result = PurgeResult(hotel_code=hotel.code, scopes=selected, dry_run=dry_run)
    steps: list[tuple[str, Callable[..., None]]] = []

    if SCOPE_RESERVATIONS in selected:
        steps.append((SCOPE_RESERVATIONS, _purge_reservations))
    if SCOPE_OPERATIONS in selected:
        steps.append((SCOPE_OPERATIONS, _purge_operations))
    if SCOPE_INVENTORY in selected:
        steps.append((SCOPE_INVENTORY, _purge_inventory))
    if SCOPE_ACCOUNTING in selected:
        steps.append((SCOPE_ACCOUNTING, _purge_accounting))
    if SCOPE_STAFF in selected:
        steps.append((SCOPE_STAFF, _purge_staff))
    if SCOPE_GUESTS in selected:
        steps.append((SCOPE_GUESTS, _purge_guests))
    if SCOPE_ROOMS in selected:
        steps.append((SCOPE_ROOMS, _purge_rooms))

    with transaction.atomic():
        for _scope_name, fn in steps:
            fn(hotel, dry_run=dry_run, deleted=result.deleted)
        if reset_sequences and SCOPE_RESERVATIONS in selected:
            _reset_sequences(hotel, dry_run=dry_run)

    return result
