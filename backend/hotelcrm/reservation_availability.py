"""Oda bazlı rezervasyon çakışması — yarı-açık tarih aralığı [check_in, check_out)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError

from hotelcrm.models.enums import ReservationStatus
from hotelcrm.models.property_guest import Room
from hotelcrm.models.reservation_folio import Reservation

if TYPE_CHECKING:
    pass

BLOCKING_STATUSES = frozenset(
    {
        ReservationStatus.UPCOMING,
        ReservationStatus.CHECKED_IN,
    }
)


def date_ranges_overlap_half_open(
    a_in: date,
    a_out: date,
    b_in: date,
    b_out: date,
) -> bool:
    """[a_in, a_out) ile [b_in, b_out) kesişiyor mu."""
    return a_in < b_out and b_in < a_out


def overlapping_reservations_qs(
    *,
    room_id: UUID,
    check_in: date,
    check_out: date,
    exclude_reservation_id: UUID | None = None,
) -> QuerySet[Reservation]:
    return (
        Reservation.objects.filter(
            room_id=room_id,
            status__in=BLOCKING_STATUSES,
            check_in_date__lt=check_out,
            check_out_date__gt=check_in,
        )
        .exclude(pk=exclude_reservation_id)
        .select_related("room")
    )


def room_unavailable_message(room: Room | None = None) -> str:
    if room and room.room_number:
        return (
            f"{room.room_number} numaralı oda seçilen tarihlerde dolu. "
            "Lütfen başka oda veya tarih seçin."
        )
    return "Seçilen oda bu tarihlerde dolu. Lütfen başka oda veya tarih seçin."


def check_room_availability(
    *,
    room: Room | None,
    check_in: date | None,
    check_out: date | None,
    status: str,
    exclude_reservation_id: UUID | None = None,
    lock_room: bool = False,
) -> None:
    """Oda atanmış ve durum bloklayıcıysa çakışma yoksa döner; varsa ValidationError."""
    if not room or not check_in or not check_out:
        return
    if status not in BLOCKING_STATUSES:
        return
    if check_out <= check_in:
        raise ValidationError(
            {"check_out_date": ["Çıkış tarihi giriş tarihinden sonra olmalıdır."]},
        )

    if lock_room:
        Room.objects.select_for_update().filter(pk=room.pk).first()

    conflict = overlapping_reservations_qs(
        room_id=room.pk,
        check_in=check_in,
        check_out=check_out,
        exclude_reservation_id=exclude_reservation_id,
    ).first()
    if conflict:
        raise ValidationError({"room": [room_unavailable_message(room)]})


def require_room_for_blocking_reservation(
    *,
    instance: Reservation | None,
    room: Room | None,
    status: str,
) -> None:
    """Yeni upcoming / checked_in rezervasyonda oda atanmadan kayıt oluşturulamaz."""
    if instance is not None:
        return
    if status not in BLOCKING_STATUSES:
        return
    if room:
        return
    raise ValidationError(
        {"room": ["Rezervasyon için oda seçimi zorunludur. Oda müsait değilse başka oda veya tarih seçin."]},
    )


def merged_stay_fields(
    instance: Reservation | None,
    attrs: dict,
) -> tuple[Room | None, date | None, date | None, str]:
    if instance is None:
        room = attrs.get("room")
        check_in = attrs.get("check_in_date")
        check_out = attrs.get("check_out_date")
        status = attrs.get("status", ReservationStatus.UPCOMING)
    else:
        room = attrs["room"] if "room" in attrs else instance.room
        check_in = attrs.get("check_in_date", instance.check_in_date)
        check_out = attrs.get("check_out_date", instance.check_out_date)
        status = attrs.get("status", instance.status)
    return room, check_in, check_out, status
