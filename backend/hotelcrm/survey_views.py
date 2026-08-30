"""Anket SMS ve halka açık anket sayfası."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from hotelcrm.models import Guest, GuestFeedbackEntry, Hotel, Reservation
from hotelcrm.models.enums import ReservationStatus
from hotelcrm.permissions import HasHotelModule
from hotelcrm.models.survey import (
    STANDARD_SURVEY_QUESTIONS,
    HotelSurveySmsSettings,
    SurveyInvitation,
)
from hotelcrm.sms_service import send_sms


def _guest_display_name(guest: Guest | None, fallback: str = "") -> str:
    if not guest:
        return fallback or "Misafir"
    fn = (guest.first_name or "").strip()
    ln = (guest.last_name or "").strip()
    name = f"{fn} {ln}".strip()
    return name or fallback or "Misafir"


def _survey_link(settings: HotelSurveySmsSettings, token: UUID) -> str:
    base = (settings.public_base_url or "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/survey/{token}/"


def _render_message(template: str, *, guest_name: str, hotel_name: str, link: str) -> str:
    return (
        template.replace("{guest_name}", guest_name)
        .replace("{hotel_name}", hotel_name)
        .replace("{link}", link)
    )


def get_or_create_sms_settings(hotel: Hotel) -> HotelSurveySmsSettings:
    obj, _ = HotelSurveySmsSettings.objects.get_or_create(
        hotel=hotel,
        defaults={"public_base_url": "http://127.0.0.1:8000"},
    )
    return obj


def _recipients_for_hotel(hotel_id: UUID, mode: str, guest_ids: list | None) -> list[dict]:
    guests = Guest.objects.filter(hotel_id=hotel_id).exclude(phone="")
    if mode == "selected" and guest_ids:
        guests = guests.filter(pk__in=guest_ids)
    elif mode == "checked_in":
        res_guest_ids = Reservation.objects.filter(
            hotel_id=hotel_id,
            status=ReservationStatus.CHECKED_IN,
        ).values_list("guest_id", flat=True)
        guests = guests.filter(pk__in=[g for g in res_guest_ids if g])
    elif mode == "checked_out":
        res_guest_ids = Reservation.objects.filter(
            hotel_id=hotel_id,
            status=ReservationStatus.CHECKED_OUT,
        ).values_list("guest_id", flat=True)
        guests = guests.filter(pk__in=[g for g in res_guest_ids if g])
    elif mode == "all_guests":
        pass
    else:
        guests = guests.none()

    out = []
    for g in guests.distinct():
        phone = (g.phone or "").strip()
        if not phone:
            continue
        out.append(
            {
                "guest_id": str(g.id),
                "guest_name": _guest_display_name(g),
                "phone": phone,
            }
        )
    return out


@transaction.atomic
def _send_invitation(hotel: Hotel, guest: Guest | None, guest_name: str, phone: str, room: str = "") -> SurveyInvitation:
    settings = get_or_create_sms_settings(hotel)
    inv = SurveyInvitation.objects.create(
        hotel=hotel,
        guest=guest,
        guest_name=guest_name,
        phone=phone,
        room_number=room or "",
        status=SurveyInvitation.Status.PENDING,
    )
    link = _survey_link(settings, inv.id)
    msg = _render_message(
        settings.message_template,
        guest_name=guest_name,
        hotel_name=hotel.name or "Otelimiz",
        link=link,
    )
    inv.sms_message = msg
    result = send_sms(settings, phone, msg)
    if result.get("ok"):
        inv.status = SurveyInvitation.Status.SENT
        inv.sent_at = timezone.now()
        inv.sms_error = ""
    else:
        inv.status = SurveyInvitation.Status.FAILED
        inv.sms_error = str(result.get("detail") or "Gönderilemedi")[:500]
    inv.save()
    return inv


class SurveyStandardTemplateView(APIView):
    permission_classes = [HasHotelModule]
    required_modules = ("surveys",)

    def get(self, request, *args, **kwargs):
        return Response({"questions": STANDARD_SURVEY_QUESTIONS})


class SurveyRecipientsView(APIView):
    """GET /api/survey/recipients/?hotel=&mode=all_guests"""

    permission_classes = [HasHotelModule]
    required_modules = ("surveys",)

    def get(self, request, *args, **kwargs):
        hotel_id = request.query_params.get("hotel")
        mode = request.query_params.get("mode", "all_guests")
        if not hotel_id:
            return Response({"detail": "hotel zorunlu."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hotel_uuid = UUID(str(hotel_id))
        except ValueError:
            return Response({"detail": "Geçersiz hotel."}, status=status.HTTP_400_BAD_REQUEST)
        recipients = _recipients_for_hotel(hotel_uuid, mode, None)
        return Response({"count": len(recipients), "recipients": recipients})


class SurveySendView(APIView):
    """POST /api/survey/send/"""

    permission_classes = [HasHotelModule]
    required_modules = ("surveys",)

    def post(self, request, *args, **kwargs):
        hotel_id = request.data.get("hotel")
        mode = request.data.get("recipient_mode", "all_guests")
        guest_ids = request.data.get("guest_ids") or []

        if not hotel_id:
            return Response({"detail": "hotel zorunlu."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hotel = Hotel.objects.get(pk=UUID(str(hotel_id)))
        except (Hotel.DoesNotExist, ValueError):
            return Response({"detail": "Otel bulunamadı."}, status=status.HTTP_404_NOT_FOUND)

        settings = get_or_create_sms_settings(hotel)
        if not settings.is_enabled and settings.provider != HotelSurveySmsSettings.Provider.MOCK:
            return Response(
                {"detail": "SMS gönderimi kapalı. Ayarlardan etkinleştirin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipients = _recipients_for_hotel(hotel.id, mode, guest_ids)
        if not recipients:
            return Response(
                {"detail": "Telefonu olan uygun misafir bulunamadı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sent, failed = 0, 0
        results = []
        for row in recipients:
            guest = None
            try:
                guest = Guest.objects.get(pk=UUID(row["guest_id"]))
            except (Guest.DoesNotExist, ValueError):
                pass
            room = ""
            if guest:
                res = (
                    Reservation.objects.filter(guest=guest, hotel=hotel)
                    .order_by("-check_out_date")
                    .first()
                )
                if res and res.room:
                    room = res.room.room_number or ""
            inv = _send_invitation(
                hotel,
                guest,
                row["guest_name"],
                row["phone"],
                room,
            )
            if inv.status == SurveyInvitation.Status.SENT:
                sent += 1
            else:
                failed += 1
            results.append(
                {
                    "id": str(inv.id),
                    "guest_name": inv.guest_name,
                    "phone": inv.phone,
                    "status": inv.status,
                    "error": inv.sms_error,
                }
            )

        return Response({"sent": sent, "failed": failed, "total": len(results), "results": results})


def public_survey_page(request, token):
    inv = get_object_or_404(
        SurveyInvitation.objects.select_related("hotel"),
        pk=token,
    )
    if request.method == "POST":
        return _public_survey_submit(request, inv)

    if inv.status == SurveyInvitation.Status.COMPLETED:
        return render(
            request,
            "survey/public_form.html",
            {"invitation": inv, "completed": True, "questions": []},
        )
    if inv.opened_at is None:
        inv.opened_at = timezone.now()
        if inv.status == SurveyInvitation.Status.SENT:
            inv.status = SurveyInvitation.Status.OPENED
        inv.save(update_fields=["opened_at", "status"])
    return render(
        request,
        "survey/public_form.html",
        {
            "invitation": inv,
            "completed": False,
            "questions": STANDARD_SURVEY_QUESTIONS,
        },
    )


def _public_survey_submit(request, inv):
    if inv.status == SurveyInvitation.Status.COMPLETED:
        return render(
            request,
            "survey/public_form.html",
            {"invitation": inv, "completed": True, "questions": []},
        )

    answers = {}
    ratings = []
    for q in STANDARD_SURVEY_QUESTIONS:
        qid = q["id"]
        raw = request.POST.get(qid, "")
        if q["type"] == "rating":
            try:
                val = int(raw)
            except (TypeError, ValueError):
                val = 0
            if val < 1 or val > q.get("max", 5):
                return render(
                    request,
                    "survey/public_form.html",
                    {
                        "invitation": inv,
                        "completed": False,
                        "questions": STANDARD_SURVEY_QUESTIONS,
                        "error": f"Lütfen tüm puanları işaretleyin ({q['label']}).",
                    },
                )
            answers[qid] = val
            ratings.append(val)
        elif q["type"] == "yesno":
            answers[qid] = raw in ("yes", "evet", "1", "true")
        else:
            answers[qid] = (raw or "").strip()[:2000]

    avg = sum(ratings) / len(ratings) if ratings else 0
    inv.answers = answers
    inv.overall_score = Decimal(str(round(avg, 2)))
    inv.status = SurveyInvitation.Status.COMPLETED
    inv.completed_at = timezone.now()
    inv.save()

    comment = answers.get("comment", "")
    GuestFeedbackEntry.objects.create(
        hotel=inv.hotel,
        guest_name=inv.guest_name,
        room_number=inv.room_number or "",
        score=min(5, max(1, int(round(avg)))),
        comment=comment,
        category="Anket",
    )

    return render(
        request,
        "survey/public_form.html",
        {"invitation": inv, "completed": True, "questions": []},
    )
