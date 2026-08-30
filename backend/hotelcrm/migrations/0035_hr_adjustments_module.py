"""Yeni İK modülü: mod.hr-deductions (Kesintiler). Teşvikler personel kartında."""

from django.db import migrations


def forwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")

    code = "mod.hr-deductions"
    perm, _ = Permission.objects.get_or_create(
        code=code,
        defaults={"description": "Modül erişimi: Kesintiler"},
    )

    for src in ("mod.hr", "mod.hr-payroll"):
        hr_perm = Permission.objects.filter(code=src).first()
        if not hr_perm:
            continue
        role_ids = RolePermission.objects.filter(permission=hr_perm).values_list(
            "role_id", flat=True,
        ).distinct()
        for rid in role_ids:
            RolePermission.objects.get_or_create(
                role=Role.objects.get(pk=rid),
                permission=perm,
            )


def backwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Permission.objects.filter(code="mod.hr-deductions").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hotelcrm", "0034_rename_hotelcrm_au_occurre_0a8f2d_idx_hotelcrm_au_occurre_eb7e7e_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
