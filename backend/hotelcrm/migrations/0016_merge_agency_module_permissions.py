from collections import defaultdict

from django.db import migrations


def forwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")
    HotelModuleOverride = apps.get_model("hotelcrm", "HotelModuleOverride")

    legacy_codes = ("mod.contracts", "mod.agency-contracts")
    new_code = "mod.agency-operations"

    p_new, _ = Permission.objects.get_or_create(
        code=new_code,
        defaults={"description": "Modül erişimi: Acenta işlemleri (kontrat + sözleşme)"},
    )

    old_ids = list(Permission.objects.filter(code__in=legacy_codes).values_list("id", flat=True))
    if old_ids:
        role_ids = set(
            RolePermission.objects.filter(permission_id__in=old_ids).values_list("role_id", flat=True)
        )
        for role_id in role_ids:
            role = Role.objects.get(pk=role_id)
            RolePermission.objects.get_or_create(role=role, permission=p_new)
        RolePermission.objects.filter(permission_id__in=old_ids).delete()
        Permission.objects.filter(id__in=old_ids).delete()

    legacy_module_ids = ("contracts", "agency-contracts")
    overrides = list(HotelModuleOverride.objects.filter(module_id__in=legacy_module_ids))
    by_hotel = defaultdict(list)
    for o in overrides:
        by_hotel[o.hotel_id].append(o)
    for hotel_id, rows in by_hotel.items():
        any_disabled = any(not r.is_enabled for r in rows)
        for r in rows:
            r.delete()
        if any_disabled:
            HotelModuleOverride.objects.update_or_create(
                hotel_id=hotel_id,
                module_id="agency-operations",
                defaults={"is_enabled": False},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0015_seed_rbac_defaults"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
