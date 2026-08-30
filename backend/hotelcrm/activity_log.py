"""Merkezi kullanıcı aktivite / denetim kaydı."""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from hotelcrm.models import AuditLog, Hotel

User = get_user_model()

ACTION_LABELS_TR: dict[str, str] = {
    "login": "Giriş",
    "logout": "Çıkış",
    "module_open": "Modül açma",
    "create": "Oluşturma",
    "update": "Güncelleme",
    "delete": "Silme",
    "user_create": "Kullanıcı oluşturma",
    "modules_update": "Modül yetkisi",
    "password_reset": "Şifre sıfırlama",
    "user_detach": "Erişim kaldırma",
    "role_assign": "Rol atama",
    "open_folio_check": "Gece denetimi",
    "business_date_close": "İş günü kapanışı",
    "night_audit": "Gece denetimi",
}

RESOURCE_LABELS_TR: dict[str, str] = {
    "reservation": "Rezervasyon",
    "guest": "Misafir",
    "room": "Oda",
    "roomtype": "Oda tipi",
    "folio": "Folyo",
    "payment": "Ödeme",
    "staffmember": "Personel",
    "inventoryitem": "Stok kalemi",
    "purchaseorder": "Satın alma",
    "journalentry": "Muhasebe fişi",
    "invoice": "Fatura",
    "housekeepingtask": "Temizlik görevi",
    "maintenanceticket": "Teknik arıza",
    "laundryorder": "Çamaşırhane",
    "posorder": "POS siparişi",
    "minibarconsumption": "Minibar",
    "surveyinvitation": "Anket daveti",
    "userrole": "Rol ataması",
    "hotelmoduleoverride": "Modül ayarı",
    "hotel-recruitment": "İşe alım",
    "night-audit": "Gece denetimi",
    "access": "Kullanıcı erişimi",
}

METHOD_VERB_TR = {
    "POST": "oluşturdu",
    "PUT": "güncelledi",
    "PATCH": "güncelledi",
    "DELETE": "sildi",
}


def client_ip(request: HttpRequest | None) -> str:
    if request is None:
        return ""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45]


def extract_hotel_id(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    for key in ("HTTP_X_HOTEL_ID",):
        raw = (request.META.get(key) or "").strip()
        if raw:
            return raw
    for key in ("hotel", "hotel_id"):
        raw = (request.GET.get(key) or "").strip()
        if raw:
            return raw
    cached = getattr(request, "_activity_hotel_id", None)
    if cached:
        return str(cached)
    if request.method in ("POST", "PUT", "PATCH") and request.content_type.startswith("application/json"):
        try:
            body = getattr(request, "_activity_body_cache", None)
            if body is None and request.body:
                body = json.loads(request.body.decode("utf-8"))
                request._activity_body_cache = body  # noqa: SLF001
            if isinstance(body, dict):
                for k in ("hotel", "hotel_id"):
                    if body.get(k):
                        return str(body[k]).strip()
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            pass
    return None


def _resolve_hotel(hotel_id: str | UUID | None):
    if not hotel_id:
        return None
    try:
        return Hotel.objects.filter(pk=UUID(str(hotel_id))).first()
    except (ValueError, TypeError):
        return None


def log_activity(
    *,
    action: str,
    message: str,
    module: str = "system",
    actor=None,
    actor_label: str = "",
    hotel_id: str | UUID | None = None,
    request: HttpRequest | None = None,
    target_user=None,
    target_user_label: str = "",
    entity_type: str = "",
    entity_id: str = "",
) -> AuditLog | None:
    if request is not None:
        if not actor and getattr(request, "user", None) and request.user.is_authenticated:
            actor = request.user
        if not actor_label and actor:
            actor_label = actor.username
        if not hotel_id:
            hotel_id = extract_hotel_id(request)

    if not actor_label and actor:
        actor_label = getattr(actor, "username", "") or ""

    hotel = _resolve_hotel(hotel_id)
    ip = client_ip(request)

    try:
        return AuditLog.objects.create(
            user=actor if getattr(actor, "is_authenticated", True) else None,
            user_label=actor_label[:128],
            hotel=hotel,
            target_user=target_user,
            target_user_label=(target_user_label or (getattr(target_user, "username", "") if target_user else ""))[
                :128
            ],
            ip_address=ip,
            entity_type=(entity_type or "")[:64],
            entity_id=(entity_id or "")[:128],
            module=(module or "system")[:64],
            action=(action or "")[:32],
            message=(message or "")[:2000],
        )
    except Exception:
        return None


def action_label_tr(action: str) -> str:
    return ACTION_LABELS_TR.get(action or "", action or "İşlem")


def module_label_tr(module: str) -> str:
    if not module:
        return "Sistem"
    if module == "api":
        return "API işlemi"
    if module == "auth":
        return "Oturum"
    if module == "user_access":
        return "Kullanıcı yönetimi"
    if module == "activity":
        return "Kullanıcı aktivitesi"
    return module.replace("-", " ").replace("_", " ").title()


def describe_api_mutation(request: HttpRequest, response_status: int) -> tuple[str, str, str] | None:
    """POST/PATCH/DELETE için (action, module, message) veya None."""
    if response_status >= 400:
        return None
    method = request.method.upper()
    if method not in METHOD_VERB_TR:
        return None

    path = request.path or ""
    if not path.startswith("/api/"):
        return None

    skip = (
        "/api/auth/refresh",
        "/api/auth/session",
        "/api/access/activity",
        "/api/access/audit-logs",
        "/api/it-monitor/heartbeat",
        "/api/it-monitor/collect-local",
        "/api/it-monitor/summary",
        "/api/assistant/chat",
    )
    if any(path.startswith(p) for p in skip):
        return None

    parts = [p for p in path.strip("/").split("/") if p]
    resource = parts[1] if len(parts) > 1 else ""
    resource_key = resource.replace("-", "").lower()
    label = RESOURCE_LABELS_TR.get(resource, RESOURCE_LABELS_TR.get(resource_key))
    if not label:
        label = resource.replace("-", " ").title() if resource else "Kayıt"

    entity_id = ""
    if len(parts) >= 3 and parts[2] not in ("",):
        if re.match(r"^[\w-]+$", parts[2]):
            entity_id = parts[2][:128]

    verb = METHOD_VERB_TR[method]
    action = {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}[method]
    detail = f" ({entity_id})" if entity_id else ""
    message = f"{label}{detail} {verb}"
    return action, "api", message


def serialize_audit_row(row: AuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "occurred_at": row.occurred_at.isoformat(),
        "user_id": row.user_id,
        "user_label": row.user_label,
        "target_user_id": row.target_user_id,
        "target_user_label": row.target_user_label,
        "ip_address": row.ip_address,
        "hotel_id": str(row.hotel_id) if row.hotel_id else None,
        "module": row.module,
        "module_label": module_label_tr(row.module),
        "action": row.action,
        "action_label": action_label_tr(row.action),
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "message": row.message,
        "category": _category_for_row(row),
    }


def _category_for_row(row: AuditLog) -> str:
    if row.module == "auth":
        return "auth"
    if row.module == "user_access":
        return "access"
    if row.action == "module_open":
        return "module"
    if row.module == "api":
        return "api"
    if row.module == "night_audit":
        return "night"
    return "other"
