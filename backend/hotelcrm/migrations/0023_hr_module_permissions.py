"""Yeni İK modülleri için permission'lar.

`mod.hr` erişimi olan rollere, alt İK modülleri (panel, vardiya, izin,
bordro, eğitim, performans, işe alım) için erişim eklenir. Böylece IK
sorumlusu yeni modülleri kutudan çıkar çıkmaz görür.
"""

from django.db import migrations


NEW_HR_MODULES = (
    ("hr-dashboard", "İK Paneli"),
    ("hr-shifts", "Vardiya & Devam"),
    ("hr-leave", "İzin Yönetimi"),
    ("hr-payroll", "Bordro & Maaş"),
    ("hr-training", "Eğitim & Sertifika"),
    ("hr-performance", "Performans & Disiplin"),
    ("hr-recruitment", "İşe Alım"),
)


def forwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")

    hr_perm = Permission.objects.filter(code="mod.hr").first()
    inheriting_role_ids = []
    if hr_perm:
        inheriting_role_ids = list(
            RolePermission.objects.filter(permission=hr_perm).values_list(
                "role_id", flat=True,
            ).distinct(),
        )

    for mid, label in NEW_HR_MODULES:
        code = f"mod.{mid}"
        perm, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": f"Modül erişimi: {label}"},
        )
        for rid in inheriting_role_ids:
            RolePermission.objects.get_or_create(
                role=Role.objects.get(pk=rid),
                permission=perm,
            )


def backwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Permission.objects.filter(
        code__in=[f"mod.{mid}" for mid, _ in NEW_HR_MODULES],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0022_staffmember_hr_profile"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
