"""Otel kullanıcıları: oluşturma, şifre, modül erişimi, denetim kaydı."""

from __future__ import annotations

from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Q

from hotelcrm.activity_log import log_activity, serialize_audit_row
from hotelcrm.models import AuditLog, Hotel, Permission, Role, UserModuleGrant, UserRole
from hotelcrm.pms_module_ids import PMS_MODULE_IDS
from hotelcrm.permissions import HasHotelModule
from hotelcrm.rbac import can_manage_users, explicit_module_grants, visible_module_ids

User = get_user_model()

MODULE_PRESETS = {
    "restaurant": [
        "dashboard",
        "fnb-dashboard",
        "fnb-outlets",
        "room-service",
        "pos",
        "recipes",
        "bar-cellar",
        "minibar",
    ],
    "housekeeping": [
        "dashboard",
        "housekeeping",
        "tech-service",
        "laundry",
        "lost-found",
        "room-rack",
        "room-inventory-admin",
    ],
    "front_office": [
        "dashboard",
        "front-office",
        "res-list",
        "res-card",
        "new-reservation",
        "room-rack",
        "folio",
        "checkout",
        "kbs",
        "cash-desk",
        "guest-inform",
    ],
    "finance": [
        "dashboard",
        "finance",
        "accounting",
        "cash-desk",
        "night-audit",
        "budget",
        "cost-control",
        "folio",
        "checkout",
    ],
}


def _ensure_module_permissions() -> None:
    for mid in PMS_MODULE_IDS:
        Permission.objects.get_or_create(
            code=f"mod.{mid}",
            defaults={"description": f"Modül erişimi: {mid}"},
        )


def _write_audit(request, hotel_id, action: str, message: str, target_user=None) -> None:
    log_activity(
        action=action,
        message=message,
        module="user_access",
        request=request,
        hotel_id=hotel_id,
        target_user=target_user,
        entity_type="user",
        entity_id=str(getattr(target_user, "pk", "") or ""),
    )


def _set_user_role(user, hotel_id, role_id) -> None:
    if role_id in (None, "", False):
        UserRole.objects.filter(user=user, hotel_id=hotel_id).delete()
        return
    try:
        rid = int(role_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Geçersiz rol.") from exc
    role = Role.objects.filter(pk=rid).first()
    if not role:
        raise ValueError("Rol bulunamadı.")
    UserRole.objects.update_or_create(
        user=user,
        hotel_id=hotel_id,
        defaults={"role": role},
    )


def _hotel_user_ids(hotel_id) -> set[int]:
    from_role = UserRole.objects.filter(hotel_id=hotel_id).values_list("user_id", flat=True)
    from_grant = UserModuleGrant.objects.filter(hotel_id=hotel_id).values_list("user_id", flat=True)
    return set(from_role) | set(from_grant)


def _serialize_hotel_user(user, hotel_id) -> dict:
    grants = sorted(explicit_module_grants(user, hotel_id))
    ur = UserRole.objects.filter(user=user, hotel_id=hotel_id).select_related("role").first()
    vis = visible_module_ids(user, hotel_id)
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "is_active": user.is_active,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "module_ids": grants,
        "visible_module_ids": vis,
        "role": (
            {"id": ur.role_id, "code": ur.role.code, "name": ur.role.name}
            if ur
            else None
        ),
    }


def _set_user_modules(user, hotel_id, module_ids: list[str]) -> None:
    pool = set(PMS_MODULE_IDS)
    clean = []
    seen = set()
    for mid in module_ids:
        m = str(mid).strip()
        if m and m in pool and m not in seen:
            seen.add(m)
            clean.append(m)
    UserModuleGrant.objects.filter(user=user, hotel_id=hotel_id).delete()
    UserModuleGrant.objects.bulk_create(
        [UserModuleGrant(user=user, hotel_id=hotel_id, module_id=m) for m in clean]
    )


class AccessHotelUsersView(APIView):
    """GET/POST /api/access/hotel-users/?hotel="""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        hotel_id = request.query_params.get("hotel")
        if not hotel_id or not can_manage_users(request.user, hotel_id):
            return Response({"detail": "Yetkisiz"}, status=status.HTTP_403_FORBIDDEN)
        ids = _hotel_user_ids(hotel_id)
        users = User.objects.filter(pk__in=ids).order_by("username")
        return Response([_serialize_hotel_user(u, hotel_id) for u in users])

    @transaction.atomic
    def post(self, request):
        hotel_id = request.data.get("hotel")
        if not hotel_id or not can_manage_users(request.user, hotel_id):
            return Response({"detail": "Yetkisiz"}, status=status.HTTP_403_FORBIDDEN)

        try:
            hotel = Hotel.objects.get(pk=UUID(str(hotel_id)))
        except (Hotel.DoesNotExist, ValueError):
            return Response({"detail": "Otel bulunamadı."}, status=status.HTTP_404_NOT_FOUND)

        username = (request.data.get("username") or "").strip().lower()
        password = request.data.get("password") or ""
        module_ids = request.data.get("module_ids") or []
        role_id = request.data.get("role_id")

        if not username or len(username) < 3:
            return Response({"detail": "Kullanıcı adı en az 3 karakter."}, status=400)
        if len(password) < 6:
            return Response({"detail": "Şifre en az 6 karakter."}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({"detail": "Bu kullanıcı adı kullanılıyor."}, status=400)
        if not module_ids and role_id in (None, ""):
            return Response({"detail": "Rol veya en az bir modül seçin."}, status=400)

        _ensure_module_permissions()
        user = User.objects.create_user(
            username=username,
            password=password,
            email=(request.data.get("email") or "").strip(),
            first_name=(request.data.get("first_name") or "").strip(),
            last_name=(request.data.get("last_name") or "").strip(),
            is_active=request.data.get("is_active", True),
        )
        if role_id not in (None, ""):
            try:
                _set_user_role(user, hotel.id, role_id)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
        if module_ids:
            _set_user_modules(user, hotel.id, module_ids)
        role_label = ""
        ur = UserRole.objects.filter(user=user, hotel_id=hotel.id).select_related("role").first()
        if ur:
            role_label = f" — rol: {ur.role.name}"
        mods_label = f" — modüller: {', '.join(module_ids)}" if module_ids else ""
        _write_audit(
            request,
            hotel.id,
            "user_create",
            f"Kullanıcı oluşturuldu: {username}{role_label}{mods_label}",
            target_user=user,
        )
        return Response(_serialize_hotel_user(user, hotel.id), status=status.HTTP_201_CREATED)


class AccessHotelUserDetailView(APIView):
    """PATCH/DELETE /api/access/hotel-users/<user_id>/?hotel="""

    permission_classes = [IsAuthenticated]

    def _get_user(self, user_id, hotel_id):
        try:
            user = User.objects.get(pk=int(user_id))
        except (User.DoesNotExist, ValueError, TypeError):
            return None, Response({"detail": "Kullanıcı bulunamadı."}, status=404)
        if user.is_superuser:
            return None, Response({"detail": "Süper kullanıcı düzenlenemez."}, status=400)
        return user, None

    @transaction.atomic
    def patch(self, request, user_id):
        hotel_id = request.query_params.get("hotel") or request.data.get("hotel")
        if not hotel_id or not can_manage_users(request.user, hotel_id):
            return Response({"detail": "Yetkisiz"}, status=status.HTTP_403_FORBIDDEN)

        user, err = self._get_user(user_id, hotel_id)
        if err:
            return err

        if "role_id" in request.data:
            try:
                _set_user_role(user, hotel_id, request.data.get("role_id"))
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            _write_audit(
                request,
                hotel_id,
                "role_assign",
                f"{user.username} rolü güncellendi",
                target_user=user,
            )

        if "module_ids" in request.data:
            _ensure_module_permissions()
            _set_user_modules(user, hotel_id, request.data.get("module_ids") or [])
            _write_audit(
                request,
                hotel_id,
                "modules_update",
                f"{user.username} modül listesi güncellendi",
                target_user=user,
            )

        if "password" in request.data and request.data["password"]:
            pw = str(request.data["password"])
            if len(pw) < 6:
                return Response({"detail": "Şifre en az 6 karakter."}, status=400)
            user.set_password(pw)
            _write_audit(
                request,
                hotel_id,
                "password_reset",
                f"{user.username} şifre sıfırlandı",
                target_user=user,
            )

        for field in ("email", "first_name", "last_name", "is_active"):
            if field in request.data:
                setattr(user, field, request.data[field])
        user.save()

        return Response(_serialize_hotel_user(user, hotel_id))

    @transaction.atomic
    def delete(self, request, user_id):
        hotel_id = request.query_params.get("hotel")
        if not hotel_id or not can_manage_users(request.user, hotel_id):
            return Response({"detail": "Yetkisiz"}, status=status.HTTP_403_FORBIDDEN)

        user, err = self._get_user(user_id, hotel_id)
        if err:
            return err

        UserModuleGrant.objects.filter(user=user, hotel_id=hotel_id).delete()
        UserRole.objects.filter(user=user, hotel_id=hotel_id).delete()
        _write_audit(
            request,
            hotel_id,
            "user_detach",
            f"{user.username} otel erişimi kaldırıldı",
            target_user=user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccessModulePresetsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hotel_id = request.query_params.get("hotel")
        if not hotel_id or not can_manage_users(request.user, hotel_id):
            return Response({"detail": "Yetkisiz"}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "presets": [
                    {"id": k, "label": k.replace("_", " ").title(), "module_ids": v}
                    for k, v in MODULE_PRESETS.items()
                ]
            }
        )


class AccessActivityView(APIView):
    """POST /api/access/activity/ — masaüstü modül açma vb. olaylar."""

    permission_classes = [HasHotelModule]
    required_modules = ()

    def post(self, request):
        hotel_id = request.data.get("hotel")
        if not hotel_id:
            return Response({"detail": "hotel gerekli."}, status=400)

        action = (request.data.get("action") or "module_open").strip()
        module_id = (request.data.get("module_id") or "").strip()
        message = (request.data.get("message") or "").strip()

        if action == "module_open" and module_id:
            label = module_id.replace("-", " ").title()
            message = message or f"{label} modülünü açtı"
            log_activity(
                action="module_open",
                message=message,
                module="activity",
                entity_type="module",
                entity_id=module_id,
                request=request,
                hotel_id=hotel_id,
            )
        elif message:
            log_activity(
                action=action or "custom",
                message=message,
                module="activity",
                request=request,
                hotel_id=hotel_id,
            )
        else:
            return Response({"detail": "message veya module_id gerekli."}, status=400)

        return Response({"ok": True})


class AccessAuditLogView(APIView):
    """GET /api/access/audit-logs/?hotel= — otel kullanıcı aktivite günlüğü."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        hotel_id = request.query_params.get("hotel")
        if not hotel_id or not can_manage_users(request.user, hotel_id):
            return Response({"detail": "Yetkisiz"}, status=status.HTTP_403_FORBIDDEN)

        try:
            UUID(str(hotel_id))
        except ValueError:
            return Response({"detail": "Geçersiz otel."}, status=400)

        user_ids = _hotel_user_ids(hotel_id)
        usernames = list(
            User.objects.filter(pk__in=user_ids).values_list("username", flat=True)
        )

        qs = (
            AuditLog.objects.select_related("user", "target_user", "hotel")
            .filter(
                Q(hotel_id=hotel_id)
                | Q(user_id__in=user_ids)
                | Q(target_user_id__in=user_ids)
                | Q(user_label__in=usernames)
                | Q(target_user_label__in=usernames)
            )
            .distinct()
        )

        category = (request.query_params.get("category") or "all").strip()
        if category == "auth":
            qs = qs.filter(module="auth")
        elif category == "access":
            qs = qs.filter(module="user_access")
        elif category == "module":
            qs = qs.filter(action="module_open")
        elif category == "api":
            qs = qs.filter(module="api")
        elif category == "night":
            qs = qs.filter(module="night_audit")

        user_filter = (request.query_params.get("user") or "").strip()
        if user_filter:
            qs = qs.filter(
                Q(user_label__iexact=user_filter)
                | Q(user__username__iexact=user_filter)
                | Q(target_user_label__iexact=user_filter)
                | Q(target_user__username__iexact=user_filter)
            )

        try:
            limit = min(max(int(request.query_params.get("limit", 300)), 1), 500)
        except (TypeError, ValueError):
            limit = 300

        rows = list(qs.order_by("-occurred_at")[:limit])

        today_actions = {}
        for r in rows[:100]:
            cat = r.module or "other"
            today_actions[cat] = today_actions.get(cat, 0) + 1

        return Response(
            {
                "logs": [serialize_audit_row(r) for r in rows],
                "stats": {
                    "total": len(rows),
                    "by_module": today_actions,
                    "active_users_today": len(
                        {r.user_label for r in rows if r.user_label}
                    ),
                },
            }
        )
