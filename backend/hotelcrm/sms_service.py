"""SMS gönderimi — mock, Netgsm, HTTP webhook."""

from __future__ import annotations

import logging
from typing import Any

import requests

from hotelcrm.models.survey import HotelSurveySmsSettings

logger = logging.getLogger(__name__)


def normalize_phone_tr(phone: str) -> str:
    digits = "".join(c for c in str(phone or "") if c.isdigit())
    if digits.startswith("90") and len(digits) >= 12:
        return digits
    if digits.startswith("0") and len(digits) >= 11:
        return "90" + digits[1:]
    if len(digits) == 10:
        return "90" + digits
    return digits


def send_sms(settings: HotelSurveySmsSettings, phone: str, message: str) -> dict[str, Any]:
    if not settings.is_enabled:
        return {"ok": False, "detail": "SMS gönderimi kapalı."}

    normalized = normalize_phone_tr(phone)
    if len(normalized) < 11:
        return {"ok": False, "detail": "Geçersiz telefon numarası."}

    provider = settings.provider or HotelSurveySmsSettings.Provider.MOCK

    if provider == HotelSurveySmsSettings.Provider.MOCK:
        logger.info("SMS [mock] → %s: %s", normalized, message[:120])
        return {"ok": True, "detail": "Test modu — mesaj konsola yazıldı.", "provider": "mock"}

    if provider == HotelSurveySmsSettings.Provider.NETGSM:
        return _send_netgsm(settings, normalized, message)

    if provider == HotelSurveySmsSettings.Provider.HTTP:
        return _send_http_webhook(settings, normalized, message)

    return {"ok": False, "detail": f"Bilinmeyen sağlayıcı: {provider}"}


def _send_netgsm(settings: HotelSurveySmsSettings, phone: str, message: str) -> dict[str, Any]:
    user = (settings.api_username or "").strip()
    password = (settings.api_password or "").strip()
    header = (settings.sender_id or "").strip()
    if not user or not password:
        return {"ok": False, "detail": "Netgsm kullanıcı adı ve şifre gerekli."}

    try:
        resp = requests.get(
            "https://api.netgsm.com.tr/sms/send/get",
            params={
                "usercode": user,
                "password": password,
                "gsmno": phone,
                "message": message,
                "msgheader": header,
                "dil": "TR",
            },
            timeout=15,
        )
        body = (resp.text or "").strip()
        ok = resp.ok and body.startswith("00")
        return {
            "ok": ok,
            "detail": body[:200] if body else resp.reason,
            "provider": "netgsm",
        }
    except requests.RequestException as exc:
        return {"ok": False, "detail": str(exc)[:200], "provider": "netgsm"}


def _send_http_webhook(settings: HotelSurveySmsSettings, phone: str, message: str) -> dict[str, Any]:
    url = (settings.webhook_url or "").strip()
    if not url:
        return {"ok": False, "detail": "Webhook URL boş."}
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json"}
    if settings.api_password:
        headers["Authorization"] = f"Bearer {settings.api_password}"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        return {
            "ok": resp.ok,
            "detail": (resp.text or "")[:200],
            "provider": "http",
        }
    except requests.RequestException as exc:
        return {"ok": False, "detail": str(exc)[:200], "provider": "http"}
