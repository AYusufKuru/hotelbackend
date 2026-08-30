"""
Gece raporu (night audit) — gerçek DB işlemleri: denetim kaydı, kasa özeti, yevmiye satırı, KBS uyarısı.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from hotelcrm.activity_log import serialize_audit_row
from hotelcrm.permissions import HasHotelModule

from .models import (
    AuditLog,
    CashTransaction,
    GLAccount,
    Hotel,
    JournalEntry,
    KbsGuestSubmission,
    Notification,
    Reservation,
    Room,
)
from .models.enums import CashFlowType, ReservationStatus, RoomOccupancyStatus


def _parse_date(s: str | None) -> date:
    if not s:
        return timezone.localdate()
    try:
        y, m, d = s.split("-")[:3]
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return timezone.localdate()


class NightAuditRunView(APIView):
    """
    POST /api/night-audit/run/
    Body: { "hotel": "<uuid>", "business_date": "YYYY-MM-DD" (opsiyonel), "force": false }
    """

    permission_classes = [HasHotelModule]
    required_modules = ("night-audit",)

    def post(self, request, *args, **kwargs):
        hotel_id = request.data.get("hotel")
        if not hotel_id:
            return Response({"detail": "hotel gerekli"}, status=400)

        try:
            hotel = Hotel.objects.get(pk=hotel_id)
        except Hotel.DoesNotExist:
            return Response({"detail": "Otel bulunamadı"}, status=404)

        business_date = _parse_date(request.data.get("business_date"))
        force = bool(request.data.get("force"))

        user = request.user if not isinstance(request.user, AnonymousUser) else None
        user_label = getattr(user, "get_username", lambda: "")() if user else "api"

        open_qs = Reservation.objects.filter(
            hotel=hotel,
            status=ReservationStatus.CHECKED_IN,
            balance_amount__gt=0,
        )
        open_count = open_qs.count()

        if open_count > 0 and not force:
            return Response(
                {
                    "blocked": True,
                    "detail": (
                        f"{open_count} misafirin açık borcu var. Tahsilat alın veya "
                        "`force: true` ile yine de çalıştırın."
                    ),
                    "open_folio_count": open_count,
                },
                status=400,
            )

        steps: list[dict] = []
        summary: dict = {}

        with transaction.atomic():
            # 1) Açık folio kontrolü
            msg1 = (
                f"{open_count} açık folio (borçlu iç misafir)"
                if open_count
                else "Açık borçlu folio yok"
            )
            AuditLog.objects.create(
                hotel=hotel,
                user=user,
                user_label=user_label,
                module="night_audit",
                action="open_folio_check",
                message=f"{business_date} — {msg1}",
            )
            steps.append(
                {
                    "id": 1,
                    "name": "Açık Folio Kontrolü",
                    "ok": True,
                    "detail": msg1,
                }
            )

            # 2) Gece sayacı / iş günü — otel üzerinde anlamsal onay (sayı tutulmuyorsa log)
            AuditLog.objects.create(
                hotel=hotel,
                user=user,
                user_label=user_label,
                module="night_audit",
                action="business_date_close",
                message=f"İş günü kapanışı: {business_date}",
            )
            steps.append(
                {
                    "id": 2,
                    "name": "Gece Sayacı",
                    "ok": True,
                    "detail": f"İş günü {business_date} kapatıldı",
                }
            )

            # 3) Oda durumu özeti
            room_stats = Room.objects.filter(hotel=hotel).aggregate(
                total=Count("id"),
                occupied=Count(
                    "id",
                    filter=Q(occupancy_status=RoomOccupancyStatus.OCCUPIED),
                ),
                vacant=Count(
                    "id",
                    filter=Q(occupancy_status=RoomOccupancyStatus.VACANT),
                ),
                ooo=Count(
                    "id",
                    filter=Q(occupancy_status=RoomOccupancyStatus.OUT_OF_ORDER),
                ),
            )
            room_msg = (
                f"Toplam {room_stats['total']} oda — "
                f"dolu {room_stats['occupied']}, boş {room_stats['vacant']}, arızalı {room_stats['ooo']}"
            )
            AuditLog.objects.create(
                hotel=hotel,
                user=user,
                user_label=user_label,
                module="night_audit",
                action="room_status_snapshot",
                message=room_msg,
            )
            steps.append(
                {
                    "id": 3,
                    "name": "Oda Durumu Raporu",
                    "ok": True,
                    "detail": room_msg,
                }
            )

            # 4) Kasa özeti + yevmiye
            agg = CashTransaction.objects.filter(
                hotel=hotel,
                tx_date=business_date,
            ).aggregate(
                gelir=Sum(
                    "amount",
                    filter=Q(flow_type=CashFlowType.INCOME),
                ),
                gider=Sum(
                    "amount",
                    filter=Q(flow_type=CashFlowType.EXPENSE),
                ),
            )
            total_gelir = agg["gelir"] or Decimal("0")
            total_gider = agg["gider"] or Decimal("0")
            net = total_gelir - total_gider

            AuditLog.objects.create(
                hotel=hotel,
                user=user,
                user_label=user_label,
                module="night_audit",
                action="cash_summary",
                message=(
                    f"Kasa {business_date}: gelir {total_gelir} ₺, gider {total_gider} ₺, net {net} ₺"
                ),
            )

            journal_id = None
            gl = GLAccount.objects.filter(hotel=hotel).first()
            if gl and net != 0:
                je = JournalEntry.objects.create(
                    hotel=hotel,
                    entry_date=business_date,
                    description=f"Gece raporu — {business_date} kasa net özeti",
                    account_code=gl.code,
                    debit_amount=net if net > 0 else None,
                    credit_amount=-net if net < 0 else None,
                )
                journal_id = str(je.id)
            elif not gl:
                AuditLog.objects.create(
                    hotel=hotel,
                    user=user,
                    user_label=user_label,
                    module="night_audit",
                    action="journal_skipped",
                    message="GL hesabı yok; yevmiye satırı oluşturulmadı",
                )
            elif gl and net == 0:
                AuditLog.objects.create(
                    hotel=hotel,
                    user=user,
                    user_label=user_label,
                    module="night_audit",
                    action="journal_skipped",
                    message=f"{business_date} net kasa 0; yevmiye satırı oluşturulmadı",
                )

            jdetail = f"Günlük kasa: gelir ₺{total_gelir}, gider ₺{total_gider}, net ₺{net}"
            if journal_id:
                jdetail += f" — yevmiye {journal_id}"
            elif not gl:
                jdetail += " — yevmiye atlandı (GL hesabı yok)"
            elif net == 0:
                jdetail += " — yevmiye atlandı (net sıfır)"
            steps.append(
                {
                    "id": 4,
                    "name": "Gelir Kaydı",
                    "ok": True,
                    "detail": jdetail,
                }
            )

            summary["total_gelir"] = str(total_gelir)
            summary["total_gider"] = str(total_gider)
            summary["net"] = str(net)
            summary["journal_entry_id"] = journal_id

            # 5) KBS: check-in olan, gönderilmemiş
            checked_in = Reservation.objects.filter(
                hotel=hotel,
                status=ReservationStatus.CHECKED_IN,
            )
            sent_res = KbsGuestSubmission.objects.filter(
                reservation__in=checked_in,
            ).values_list("reservation_id", flat=True)
            pending_kbs = checked_in.exclude(pk__in=sent_res).count()
            kbs_msg = (
                f"{pending_kbs} iç misafir için KBS bildirimi eksik"
                if pending_kbs
                else "KBS: bekleyen yok"
            )
            AuditLog.objects.create(
                hotel=hotel,
                user=user,
                user_label=user_label,
                module="night_audit",
                action="kbs_check",
                message=kbs_msg,
            )
            steps.append(
                {
                    "id": 5,
                    "name": "KBS Bildirim Kontrolü",
                    "ok": pending_kbs == 0,
                    "detail": kbs_msg,
                }
            )

            # 6) Yedekleme — operasyonel hatırlatma (otomatik yedek yok)
            AuditLog.objects.create(
                hotel=hotel,
                user=user,
                user_label=user_label,
                module="night_audit",
                action="backup_reminder",
                message="Harici yedekleme / DBA politikası otel prosedürüne göre doğrulanmalıdır",
            )
            steps.append(
                {
                    "id": 6,
                    "name": "Yedekleme",
                    "ok": True,
                    "detail": "Denetim kaydı oluşturuldu; harici yedek prosedürünü uygulayın",
                }
            )

            Notification.objects.create(
                hotel=hotel,
                notif_type="success",
                message=f"Gece raporu tamamlandı — {business_date}",
            )

        return Response(
            {
                "ok": True,
                "business_date": business_date.isoformat(),
                "forced": force and open_count > 0,
                "steps": steps,
                "summary": summary,
            }
        )


class NightAuditHistoryView(APIView):
    """GET /api/night-audit/history/?hotel=&limit= — gece raporu denetim günlüğü."""

    permission_classes = [HasHotelModule]
    required_modules = ("night-audit",)

    def get(self, request):
        hotel_id = request.query_params.get("hotel")
        if not hotel_id:
            return Response({"detail": "hotel gerekli"}, status=400)
        try:
            Hotel.objects.get(pk=hotel_id)
        except Hotel.DoesNotExist:
            return Response({"detail": "Otel bulunamadı"}, status=404)

        try:
            limit = min(max(int(request.query_params.get("limit", 300)), 1), 500)
        except (TypeError, ValueError):
            limit = 300

        rows = list(
            AuditLog.objects.filter(hotel_id=hotel_id, module="night_audit")
            .order_by("-occurred_at")[:limit]
        )
        return Response({"logs": [serialize_audit_row(r) for r in rows]})
