from django.db import migrations

# Ön büro personeli: tam paket değil, mod.* ile parça erişim
_STAFF_FRONT_MODULES = (
    "dashboard",
    "front-office",
    "res-list",
    "room-rack",
    "folio",
    "checkout",
    "kbs",
    "cash-desk",
    "housekeeping",
    "tech-service",
    "night-audit",
    "res-card",
    "new-reservation",
)


def forwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")
    User = apps.get_model("auth", "User")
    UserRole = apps.get_model("hotelcrm", "UserRole")
    Hotel = apps.get_model("hotelcrm", "Hotel")

    core_defs = [
        ("modules.manage", "Otel için menü modüllerini kapatıp açma"),
        ("users.manage", "Bu otelde Django kullanıcılarına rol atama"),
        ("tasks.assign", "Operasyon görevi atama"),
        ("mod.all", "Otelde açık olan tüm modüllere erişim"),
    ]

    perm_map = {}
    for code, desc in core_defs:
        p, _ = Permission.objects.get_or_create(code=code, defaults={"description": desc})
        perm_map[code] = p

    for mid in _STAFF_FRONT_MODULES:
        code = f"mod.{mid}"
        p, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": f"Modül erişimi: {mid}"},
        )
        perm_map[code] = p

    def link_role(role, codes: list[str]) -> None:
        for c in codes:
            p = perm_map.get(c)
            if p:
                RolePermission.objects.get_or_create(role=role, permission=p)

    r_sys, _ = Role.objects.get_or_create(
        code="system_operator",
        defaults={"name": "Sistem işletmecisi"},
    )
    link_role(
        r_sys,
        ["modules.manage", "users.manage", "tasks.assign", "mod.all"],
    )

    r_owner, _ = Role.objects.get_or_create(
        code="owner",
        defaults={"name": "İşletme sahibi / patron"},
    )
    link_role(r_owner, ["users.manage", "tasks.assign", "mod.all"])

    r_staff, _ = Role.objects.get_or_create(
        code="staff_front",
        defaults={"name": "Ön büro personeli"},
    )
    staff_codes = [f"mod.{m}" for m in _STAFF_FRONT_MODULES]
    link_role(r_staff, staff_codes)

    demo = User.objects.filter(username="demo").first()
    hotel = Hotel.objects.filter(code="DEMO").first()
    if demo and hotel:
        UserRole.objects.get_or_create(
            user=demo,
            hotel=hotel,
            defaults={"role": r_sys},
        )


def backwards(apps, schema_editor):
    Role = apps.get_model("hotelcrm", "Role")
    Permission = apps.get_model("hotelcrm", "Permission")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")

    RolePermission.objects.filter(
        role__code__in=["system_operator", "owner", "staff_front"],
    ).delete()
    Role.objects.filter(code__in=["system_operator", "owner", "staff_front"]).delete()
    Permission.objects.filter(
        code__in=[
            "modules.manage",
            "users.manage",
            "tasks.assign",
            "mod.all",
        ]
        + [f"mod.{m}" for m in _STAFF_FRONT_MODULES],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0014_userrole_hotel_and_module_override"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
