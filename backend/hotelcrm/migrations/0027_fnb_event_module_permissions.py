"""Yiyecek, İçecek & Etkinlik kategorisi için yeni alt modül permission'ları.

`mod.banquet` / `mod.pos` / `mod.minibar` izinlerinden birine sahip rollere,
yeni F&B modülleri (komuta merkezi, outlet listesi, oda servisi, reçete,
bar & mahzen, toplantı & konferans) için erişim eklenir.
"""

from django.db import migrations


NEW_FNB_MODULES = (
    ("fnb-dashboard", "F&B Komuta Merkezi"),
    ("fnb-outlets", "Outlet & Restoran Listesi"),
    ("room-service", "Oda Servisi (IRD)"),
    ("recipes", "Reçete & Menü Maliyeti"),
    ("bar-cellar", "Bar & Şarap Mahzeni"),
    ("meetings", "Toplantı & Konferans"),
)

PARENT_PERM_CODES = ("mod.banquet", "mod.pos", "mod.minibar")


def forwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")

    parent_perms = list(Permission.objects.filter(code__in=PARENT_PERM_CODES))
    inheriting_role_ids = set()
    if parent_perms:
        inheriting_role_ids = set(
            RolePermission.objects.filter(permission__in=parent_perms).values_list(
                "role_id", flat=True,
            ).distinct(),
        )

    for mid, label in NEW_FNB_MODULES:
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
        code__in=[f"mod.{mid}" for mid, _ in NEW_FNB_MODULES],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0026_inventory_restaurant_pos"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
