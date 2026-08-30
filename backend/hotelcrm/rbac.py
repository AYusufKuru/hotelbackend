"""Otel + kullanıcı rolüne göre izin ve görünür modül hesaplama."""

from __future__ import annotations

from hotelcrm.models import HotelModuleOverride, RolePermission, UserModuleGrant, UserRole
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


def explicit_module_grants(user, hotel_uuid: str) -> set[str]:
    return set(
        UserModuleGrant.objects.filter(user=user, hotel_id=hotel_uuid).values_list(
            "module_id",
            flat=True,
        )
    )


def user_belongs_to_hotel(user, hotel_uuid: str) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    if UserRole.objects.filter(user=user, hotel_id=hotel_uuid).exists():
        return True
    return UserModuleGrant.objects.filter(user=user, hotel_id=hotel_uuid).exists()


def hotel_ids_for_user(user) -> set[str]:
    """Kullanıcının üye olduğu otel UUID'leri (süper kullanıcı = tüm oteller)."""
    if getattr(user, "is_superuser", False):
        from hotelcrm.models import Hotel

        return {str(pk) for pk in Hotel.objects.values_list("pk", flat=True)}
    from_role = UserRole.objects.filter(user=user).values_list("hotel_id", flat=True)
    from_grant = UserModuleGrant.objects.filter(user=user).values_list("hotel_id", flat=True)
    return {str(x) for x in from_role} | {str(x) for x in from_grant}


def user_can_use_modules(user, hotel_uuid: str, modules: tuple[str, ...] | list[str]) -> bool:
    """Menüde görebileceği herhangi bir modül bu API için yeterli."""
    if not user_belongs_to_hotel(user, hotel_uuid):
        return False
    if not modules:
        return True
    vis = set(visible_module_ids(user, hotel_uuid))
    return bool(vis.intersection(modules))


def visible_module_ids(user, hotel_uuid: str) -> list[str]:
    perms = permission_codes_for_user(user, hotel_uuid)
    pool = base_module_pool_for_hotel(hotel_uuid)
    if user.is_superuser or "modules.manage" in perms or "mod.all" in perms:
        return list(pool)

    grants = explicit_module_grants(user, hotel_uuid)
    if "user-access" in grants:
        grants.discard("user-access")
        grants.add("system-admin")
    if grants:
        out = [m for m in pool if m in grants]
    else:
        out = [m for m in pool if f"mod.{m}" in perms]

    # Rol yöneticisi menüden Sistem Yönetimi'ni görebilmeli
    if ("users.manage" in perms or "modules.manage" in perms) and "system-admin" in pool:
        if "system-admin" not in out:
            out = [*out, "system-admin"]

    if out:
        return out
    if UserRole.objects.filter(user=user, hotel_id=hotel_uuid).exists():
        return ["dashboard"] if "dashboard" in pool else []
    return []


def can_manage_modules(user, hotel_uuid: str) -> bool:
    return user.is_superuser or "modules.manage" in permission_codes_for_user(user, hotel_uuid)


def can_manage_users(user, hotel_uuid: str) -> bool:
    return user.is_superuser or "users.manage" in permission_codes_for_user(user, hotel_uuid)


def can_assign_tasks(user, hotel_uuid: str) -> bool:
    return user.is_superuser or "tasks.assign" in permission_codes_for_user(user, hotel_uuid)


def _perm_set(user, hotel_uuid: str) -> set[str]:
    return permission_codes_for_user(user, hotel_uuid)


def can_list_hotel_staff(user, hotel_uuid: str) -> bool:
    """Personel listesi / tekil kayıt okuma (İK modülü, IT kuyruk, yönetici)."""
    if user.is_superuser:
        return True
    perms = _perm_set(user, hotel_uuid)
    if perms.intersection(
        {"modules.manage", "mod.all", "users.manage", "it.onboarding", "mod.hr", "hr.staff.register"},
    ):
        return True
    return any(p.startswith("mod.hr") for p in perms)


def can_direct_manage_staff_record(user, hotel_uuid: str) -> bool:
    """İK beklemeden personel oluşturma / onboarding tamamlama / IT dışı yönetici yolu."""
    if user.is_superuser:
        return True
    return bool(
        _perm_set(user, hotel_uuid).intersection(
            {"modules.manage", "mod.all", "users.manage", "it.onboarding"},
        ),
    )
