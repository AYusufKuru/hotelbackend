"""
Merkez lisans sunucusu (admin/) ile iletişim.
LICENSE_SERVER_URL ve LICENSE_KEY boşsa kontrol yapılmaz (yerel geliştirme).
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"until": 0.0, "ok": True, "reason": ""}


@dataclass
class LicenseState:
    ok: bool
    reason: str


def _endpoint() -> str:
    base = (getattr(settings, "LICENSE_SERVER_URL", "") or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/api/v1/license/status"


def _fetch_remote() -> LicenseState:
    url = _endpoint()
    key = (getattr(settings, "LICENSE_KEY", "") or "").strip()
    if not url or not key:
        return LicenseState(ok=True, reason="")

    body = json.dumps({"license_key": key}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = float(getattr(settings, "LICENSE_CHECK_TIMEOUT", 8.0))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
    except urllib.error.HTTPError as e:
        return LicenseState(ok=False, reason=f"Lisans sunucusu HTTP {e.code}.")
    except urllib.error.URLError as e:
        return LicenseState(ok=False, reason=f"Lisans sunucusuna ulaşılamıyor: {e.reason!r}.")
    except (json.JSONDecodeError, ValueError) as e:
        return LicenseState(ok=False, reason=f"Lisans yanıtı okunamadı: {e}.")

    if data.get("ok") is True:
        return LicenseState(ok=True, reason="")
    reason = data.get("reason") or data.get("status") or "Lisans geçerli değil."
    return LicenseState(ok=False, reason=str(reason))


def get_license_state() -> LicenseState:
    """TTL önbellekli merkez sorgusu."""
    if not _endpoint() or not (getattr(settings, "LICENSE_KEY", "") or "").strip():
        return LicenseState(ok=True, reason="")

    ttl = float(getattr(settings, "LICENSE_CHECK_CACHE_SECONDS", 30))
    now = time.monotonic()
    with _cache_lock:
        if now < float(_cache["until"]):
            return LicenseState(ok=bool(_cache["ok"]), reason=str(_cache["reason"] or ""))

    state = _fetch_remote()
    # İzin verilen yanıt daha uzun önbelleklenebilir; reddedilen kısa sürede yeniden sorulsun (panelden düzeltme yansısın).
    cache_ttl = max(5.0, ttl) if state.ok else max(5.0, min(15.0, ttl))
    with _cache_lock:
        _cache["until"] = time.monotonic() + cache_ttl
        _cache["ok"] = state.ok
        _cache["reason"] = state.reason
    return state


def invalidate_license_cache() -> None:
    with _cache_lock:
        _cache["until"] = 0.0
