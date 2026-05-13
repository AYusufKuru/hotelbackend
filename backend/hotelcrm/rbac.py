"""Otel + kullanıcı rolüne göre izin ve görünür modül hesaplama."""

from __future__ import annotations

from hotelcrm.models import HotelModuleOverride, RolePermission, UserRole
from hotelcrm.pms_module_ids import PMS_MODULE_IDS


def permission_codes_for_user(user, hotel_uuid: str) -> set[str]:
    if user.is_superuser:
        return {
            "modules.manage",
            "users.manage",
            "tasks.assign",
            "mod.all",
        }
    codes: set[str] = set()
    for ur in UserRole.objects.filter(user=user, hotel_id=hotel_uuid).select_related("role"):
        for rp in RolePermission.objects.filter(role=ur.role).select_related("permission"):
            codes.add(rp.permission.code)
    return codes


def hotel_disabled_module_ids(hotel_uuid: str) -> set[str]:
    return set(
        HotelModuleOverride.objects.filter(
            hotel_id=hotel_uuid,
            is_enabled=False,
        ).values_list("module_id", flat=True),
    )


def base_module_pool_for_hotel(hotel_uuid: str) -> list[str]:
    disabled = hotel_disabled_module_ids(hotel_uuid)
    return [m for m in PMS_MODULE_IDS if m not in disabled]


def visible_module_ids(user, hotel_uuid: str) -> list[str]:
    perms = permission_codes_for_user(user, hotel_uuid)
    pool = base_module_pool_for_hotel(hotel_uuid)
    if user.is_superuser or "modules.manage" in perms or "mod.all" in perms:
        return list(pool)
    out = [m for m in pool if f"mod.{m}" in perms]
    if not out:
        return ["dashboard"]
    return out


def can_manage_modules(user, hotel_uuid: str) -> bool:
    return user.is_superuser or "modules.manage" in permission_codes_for_user(user, hotel_uuid)


def can_manage_users(user, hotel_uuid: str) -> bool:
    return user.is_superuser or "users.manage" in permission_codes_for_user(user, hotel_uuid)


def can_assign_tasks(user, hotel_uuid: str) -> bool:
    return user.is_superuser or "tasks.assign" in permission_codes_for_user(user, hotel_uuid)
