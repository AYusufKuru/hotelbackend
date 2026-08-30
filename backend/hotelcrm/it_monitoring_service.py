"""IT izleme: agent heartbeat, metrik örnekleri, eşik alarmları ve webhook teslimi."""

from __future__ import annotations

import logging
import secrets
import time
from decimal import Decimal
from typing import Any

import requests
from django.db import transaction
from django.utils import timezone

from hotelcrm.models import IntegrationConnection, ItAlertLog, ItAlarmWebhook, ItMetricSample

logger = logging.getLogger(__name__)

OFFLINE_DEFAULT_MINUTES = 5
ALERT_COOLDOWN_MINUTES = 15
METRIC_SAMPLE_RETENTION = 500


def ensure_agent_token(integration: IntegrationConnection) -> str:
    if not integration.agent_token:
        integration.agent_token = secrets.token_urlsafe(32)
        integration.save(update_fields=["agent_token"])
    return integration.agent_token


def collect_psutil_metrics(interval_sec: float = 1.0) -> dict[str, Any] | None:
    try:
        import psutil
    except ImportError:
        return None

    hostname = ""
    try:
        import socket

        hostname = socket.gethostname()
    except OSError:
        hostname = ""

    cpu_percent = float(psutil.cpu_percent(interval=0.5))
    memory_percent = float(psutil.virtual_memory().percent)
    disk_percent = float(psutil.disk_usage("/").percent)

    net_before = psutil.net_io_counters()
    time.sleep(max(0.2, interval_sec))
    net_after = psutil.net_io_counters()
    elapsed = max(interval_sec, 0.001)
    mbits_in = ((net_after.bytes_recv - net_before.bytes_recv) * 8) / elapsed / 1_000_000
    mbits_out = ((net_after.bytes_sent - net_before.bytes_sent) * 8) / elapsed / 1_000_000

    return {
        "host_hostname": hostname[:255],
        "cpu_percent": round(cpu_percent, 2),
        "memory_percent": round(memory_percent, 2),
        "disk_percent": round(disk_percent, 2),
        "network_mbps_in": round(max(0.0, mbits_in), 3),
        "network_mbps_out": round(max(0.0, mbits_out), 3),
    }


def integration_by_agent_token(token: str) -> IntegrationConnection | None:
    if not token:
        return None
    return (
        IntegrationConnection.objects.filter(agent_token=token, monitor_enabled=True)
        .select_related("hotel")
        .first()
    )


def format_uptime_label(started_at) -> str:
    if not started_at:
        return "—"
    delta = timezone.now() - started_at
    total_sec = int(delta.total_seconds())
    if total_sec < 60:
        return f"{total_sec}s"
    if total_sec < 3600:
        return f"{total_sec // 60}dk"
    if total_sec < 86400:
        return f"{total_sec // 3600}sa { (total_sec % 3600) // 60}dk"
    days = total_sec // 86400
    hours = (total_sec % 86400) // 3600
    return f"{days}g {hours}sa"


def is_integration_offline(integration: IntegrationConnection, offline_minutes: int) -> bool:
    if not integration.monitor_enabled or not integration.last_heartbeat_at:
        return integration.monitor_enabled
    cutoff = timezone.now() - timezone.timedelta(minutes=offline_minutes)
    return integration.last_heartbeat_at < cutoff


@transaction.atomic
def record_heartbeat(integration: IntegrationConnection, metrics: dict[str, Any]) -> IntegrationConnection:
    now = timezone.now()
    was_offline = (
        not integration.last_heartbeat_at
        or integration.connection_status in ("inactive", "offline", "")
    )

    integration.host_hostname = str(metrics.get("host_hostname") or integration.host_hostname or "")[:255]
    integration.cpu_percent = Decimal(str(metrics["cpu_percent"]))
    integration.memory_percent = Decimal(str(metrics["memory_percent"]))
    integration.disk_percent = Decimal(str(metrics["disk_percent"]))
    integration.network_mbps_in = Decimal(str(metrics.get("network_mbps_in", 0)))
    integration.network_mbps_out = Decimal(str(metrics.get("network_mbps_out", 0)))
    integration.last_heartbeat_at = now
    integration.connection_status = "active"
    integration.last_sync_label = format_uptime_label(integration.uptime_started_at or now)

    if was_offline or not integration.uptime_started_at:
        integration.uptime_started_at = now
        integration.last_sync_label = "0dk"

    integration.save(
        update_fields=[
            "host_hostname",
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "network_mbps_in",
            "network_mbps_out",
            "last_heartbeat_at",
            "connection_status",
            "last_sync_label",
            "uptime_started_at",
        ]
    )

    ItMetricSample.objects.create(
        integration=integration,
        cpu_percent=integration.cpu_percent,
        memory_percent=integration.memory_percent,
        disk_percent=integration.disk_percent,
        network_mbps_in=integration.network_mbps_in,
        network_mbps_out=integration.network_mbps_out,
    )

    sample_ids = list(
        ItMetricSample.objects.filter(integration=integration)
        .order_by("-recorded_at")
        .values_list("id", flat=True)[METRIC_SAMPLE_RETENTION:]
    )
    if sample_ids:
        ItMetricSample.objects.filter(id__in=sample_ids).delete()

    integration.last_sync_label = format_uptime_label(integration.uptime_started_at)
    integration.save(update_fields=["last_sync_label"])

    _evaluate_alerts(integration)
    return integration


def _recent_alert_exists(
    integration: IntegrationConnection,
    alert_kind: str,
    minutes: int = ALERT_COOLDOWN_MINUTES,
) -> bool:
    cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
    return ItAlertLog.objects.filter(
        integration=integration,
        alert_kind=alert_kind,
        created_at__gte=cutoff,
    ).exists()


def _evaluate_alerts(integration: IntegrationConnection) -> None:
    hotel = integration.hotel
    if not hotel:
        return

    webhooks = list(ItAlarmWebhook.objects.filter(hotel=hotel, is_enabled=True))
    if not webhooks:
        return

    checks: list[tuple[str, str, float]] = []
    if integration.cpu_percent is not None:
        checks.append(("cpu_high", "critical", float(integration.cpu_percent)))
    if integration.memory_percent is not None:
        checks.append(("memory_high", "warning", float(integration.memory_percent)))
    if integration.disk_percent is not None:
        checks.append(("disk_high", "critical", float(integration.disk_percent)))

    for webhook in webhooks:
        thresholds = {
            "cpu_high": webhook.cpu_threshold,
            "memory_high": webhook.memory_threshold,
            "disk_high": webhook.disk_threshold,
        }
        for alert_kind, severity, value in checks:
            threshold = thresholds.get(alert_kind, 100)
            if value < threshold:
                continue
            if _recent_alert_exists(integration, alert_kind):
                continue
            message = (
                f"{integration.name}: {alert_kind.replace('_', ' ')} "
                f"%{value:.1f} (eşik %{threshold})"
            )
            _fire_alert(integration, webhook, alert_kind, severity, message)


def check_offline_hosts_for_hotel(hotel_id) -> None:
    """Periyodik görev veya özet API için offline kontrolü."""
    integrations = IntegrationConnection.objects.filter(
        hotel_id=hotel_id,
        monitor_enabled=True,
    )
    webhooks = list(ItAlarmWebhook.objects.filter(hotel_id=hotel_id, is_enabled=True))
    if not webhooks:
        return
    for integration in integrations:
        for webhook in webhooks:
            offline_mins = webhook.offline_minutes or OFFLINE_DEFAULT_MINUTES
            if not is_integration_offline(integration, offline_mins):
                continue
            if _recent_alert_exists(integration, "host_offline"):
                continue
            message = f"{integration.name}: {offline_mins} dk heartbeat yok"
            _fire_alert(integration, webhook, "host_offline", "critical", message)


def _fire_alert(
    integration: IntegrationConnection,
    webhook: ItAlarmWebhook,
    alert_kind: str,
    severity: str,
    message: str,
) -> ItAlertLog:
    payload = {
        "event": alert_kind,
        "severity": severity,
        "message": message,
        "hotel_id": str(integration.hotel_id) if integration.hotel_id else None,
        "integration_id": str(integration.id),
        "integration_name": integration.name,
        "cpu_percent": float(integration.cpu_percent or 0),
        "memory_percent": float(integration.memory_percent or 0),
        "disk_percent": float(integration.disk_percent or 0),
        "timestamp": timezone.now().isoformat(),
    }
    headers = {"Content-Type": "application/json"}
    if webhook.secret_header:
        headers["X-It-Monitor-Secret"] = webhook.secret_header

    status = "skipped"
    response_text = ""
    if webhook.is_enabled and webhook.target_url:
        try:
            resp = requests.post(webhook.target_url, json=payload, headers=headers, timeout=8)
            status = "delivered" if resp.ok else "failed"
            response_text = (resp.text or "")[:500]
        except requests.RequestException as exc:
            status = "failed"
            response_text = str(exc)[:500]
            logger.warning("Webhook delivery failed: %s", exc)

    return ItAlertLog.objects.create(
        hotel=integration.hotel,
        integration=integration,
        webhook=webhook,
        alert_kind=alert_kind,
        severity=severity,
        message=message,
        webhook_status=status,
        webhook_response=response_text,
    )


def dispatch_test_webhook(webhook: ItAlarmWebhook) -> ItAlertLog:
    hotel = webhook.hotel
    payload = {
        "event": "test",
        "severity": "info",
        "message": f"Hoterfea IT izleme test — {webhook.name}",
        "hotel_id": str(hotel.id),
        "timestamp": timezone.now().isoformat(),
    }
    headers = {"Content-Type": "application/json"}
    if webhook.secret_header:
        headers["X-It-Monitor-Secret"] = webhook.secret_header
    status = "skipped"
    response_text = ""
    try:
        resp = requests.post(webhook.target_url, json=payload, headers=headers, timeout=8)
        status = "delivered" if resp.ok else "failed"
        response_text = (resp.text or "")[:500]
    except requests.RequestException as exc:
        status = "failed"
        response_text = str(exc)[:500]

    return ItAlertLog.objects.create(
        hotel=hotel,
        integration=None,
        webhook=webhook,
        alert_kind="test",
        severity="info",
        message=payload["message"],
        webhook_status=status,
        webhook_response=response_text,
    )
