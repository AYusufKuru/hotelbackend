"""Yeni masaüstü modülü: mod.laundry-pricelist."""

from django.db import migrations


def forwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")

    code = "mod.laundry-pricelist"
    perm, _ = Permission.objects.get_or_create(
        code=code,
        defaults={"description": "Modül erişimi: Çamaşır fiyat listesi"},
    )

    laundry_perm = Permission.objects.filter(code="mod.laundry").first()
    if laundry_perm:
        role_ids = RolePermission.objects.filter(permission=laundry_perm).values_list(
            "role_id", flat=True,
        ).distinct()
        Role = apps.get_model("hotelcrm", "Role")
        for rid in role_ids:
            RolePermission.objects.get_or_create(
                role=Role.objects.get(pk=rid),
                permission=perm,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0016_merge_agency_module_permissions"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
