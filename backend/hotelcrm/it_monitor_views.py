"""IT izleme API: agent heartbeat, yerel ölçüm, webhook testi, özet."""

from uuid import UUID

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from hotelcrm.models import IntegrationConnection, ItAlarmWebhook, ItMetricSample
from hotelcrm.permissions import HasHotelModule

from .it_monitoring_service import (
    check_offline_hosts_for_hotel,
    collect_psutil_metrics,
    dispatch_test_webhook,
    ensure_agent_token,
    integration_by_agent_token,
    is_integration_offline,
    record_heartbeat,
)


class ItMonitorHeartbeatView(APIView):
    """`POST /api/it-monitor/heartbeat/` — agent token ile metrik gönderimi."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        token = (
            request.data.get("agent_token")
            or request.headers.get("X-Agent-Token")
            or ""
        )
        integration = integration_by_agent_token(str(token).strip())
        if not integration:
            return Response({"detail": "Geçersiz agent token."}, status=status.HTTP_403_FORBIDDEN)

        metrics = {
            "host_hostname": request.data.get("host_hostname", ""),
            "cpu_percent": request.data.get("cpu_percent"),
            "memory_percent": request.data.get("memory_percent"),
            "disk_percent": request.data.get("disk_percent"),
            "network_mbps_in": request.data.get("network_mbps_in", 0),
            "network_mbps_out": request.data.get("network_mbps_out", 0),
        }
        required = ("cpu_percent", "memory_percent", "disk_percent")
        if any(metrics[k] is None for k in required):
            return Response(
                {"detail": "cpu_percent, memory_percent, disk_percent zorunlu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record_heartbeat(integration, metrics)
        return Response(
            {
                "ok": True,
                "integration_id": str(integration.id),
                "last_heartbeat_at": integration.last_heartbeat_at,
            }
        )


class ItMonitorCollectLocalView(APIView):
    """`POST /api/it-monitor/collect-local/` — Django sunucusunda psutil ölçümü."""

    permission_classes = [HasHotelModule]
    required_modules = ("it-infra",)

    def post(self, request, *args, **kwargs):
        integration_id = request.data.get("integration")
        if not integration_id:
            return Response({"detail": "integration zorunlu."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            integration = IntegrationConnection.objects.get(pk=UUID(str(integration_id)))
        except (IntegrationConnection.DoesNotExist, ValueError):
            return Response({"detail": "Kayıt bulunamadı."}, status=status.HTTP_404_NOT_FOUND)

        if not integration.monitor_enabled:
            integration.monitor_enabled = True
            ensure_agent_token(integration)
            integration.save(update_fields=["monitor_enabled"])

        metrics = collect_psutil_metrics()
        if not metrics:
            return Response(
                {"detail": "psutil yüklü değil (pip install psutil)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        record_heartbeat(integration, metrics)
        return Response({"ok": True, "metrics": metrics, "agent_token": integration.agent_token})


class ItMonitorWebhookTestView(APIView):
    """`POST /api/it-monitor/webhook-test/` — alarm webhook test gönderimi."""

    permission_classes = [HasHotelModule]
    required_modules = ("it-infra",)

    def post(self, request, *args, **kwargs):
        webhook_id = request.data.get("webhook")
        if not webhook_id:
            return Response({"detail": "webhook zorunlu."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            webhook = ItAlarmWebhook.objects.get(pk=UUID(str(webhook_id)))
        except (ItAlarmWebhook.DoesNotExist, ValueError):
            return Response({"detail": "Webhook bulunamadı."}, status=status.HTTP_404_NOT_FOUND)

        log = dispatch_test_webhook(webhook)
        return Response(
            {
                "ok": log.webhook_status == "delivered",
                "webhook_status": log.webhook_status,
                "webhook_response": log.webhook_response,
            }
        )


class ItMonitorSummaryView(APIView):
    """`GET /api/it-monitor/summary/?hotel=<uuid>` — IT paneli özet verisi."""

    permission_classes = [HasHotelModule]
    required_modules = ("it-infra",)

    def get(self, request, *args, **kwargs):
        hotel_id = request.query_params.get("hotel")
        if not hotel_id:
            return Response({"detail": "hotel zorunlu."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            hotel_uuid = UUID(str(hotel_id))
        except ValueError:
            return Response({"detail": "Geçersiz hotel."}, status=status.HTTP_400_BAD_REQUEST)

        check_offline_hosts_for_hotel(hotel_uuid)

        integrations = list(
            IntegrationConnection.objects.filter(hotel_id=hotel_uuid, monitor_enabled=True)
        )
        int_ids = [i.id for i in integrations]

        samples = list(
            ItMetricSample.objects.filter(integration_id__in=int_ids)
            .order_by("-recorded_at")[:120]
        )

        webhooks = list(ItAlarmWebhook.objects.filter(hotel_id=hotel_uuid))
        from hotelcrm.models import ItAlertLog

        alerts = list(ItAlertLog.objects.filter(hotel_id=hotel_uuid).order_by("-created_at")[:50])

        network_in = sum(float(i.network_mbps_in or 0) for i in integrations if not is_integration_offline(i, 5))
        network_out = sum(float(i.network_mbps_out or 0) for i in integrations if not is_integration_offline(i, 5))

        return Response(
            {
                "network_mbps_in": round(network_in, 3),
                "network_mbps_out": round(network_out, 3),
                "metric_samples": [
                    {
                        "integration": str(s.integration_id),
                        "cpu_percent": float(s.cpu_percent),
                        "memory_percent": float(s.memory_percent),
                        "disk_percent": float(s.disk_percent),
                        "network_mbps_in": float(s.network_mbps_in),
                        "network_mbps_out": float(s.network_mbps_out),
                        "recorded_at": s.recorded_at.isoformat(),
                    }
                    for s in reversed(samples)
                ],
                "webhooks": [
                    {
                        "id": str(w.id),
                        "name": w.name,
                        "target_url": w.target_url,
                        "is_enabled": w.is_enabled,
                        "cpu_threshold": w.cpu_threshold,
                        "memory_threshold": w.memory_threshold,
                        "disk_threshold": w.disk_threshold,
                        "offline_minutes": w.offline_minutes,
                    }
                    for w in webhooks
                ],
                "alerts": [
                    {
                        "id": a.id,
                        "alert_kind": a.alert_kind,
                        "severity": a.severity,
                        "message": a.message,
                        "webhook_status": a.webhook_status,
                        "created_at": a.created_at.isoformat(),
                        "integration": str(a.integration_id) if a.integration_id else None,
                    }
                    for a in alerts
                ],
            }
        )
