from django.db import migrations

# pms_module_ids.PMS_MODULE_IDS ile aynı sıra — migration içinde import etmeyin
_ALL_MODULE_IDS = (
    "dashboard",
    "global-vision",
    "ai-strategy",
    "revenue",
    "reservations-tape",
    "new-reservation",
    "front-office",
    "folio",
    "kbs",
    "cash-desk",
    "housekeeping",
    "crm",
    "guest-inform",
    "loyalty",
    "banquet",
    "fnb-dashboard",
    "fnb-outlets",
    "room-service",
    "recipes",
    "bar-cellar",
    "meetings",
    "tech-service",
    "stock",
    "purchasing",
    "hr",
    "hr-dashboard",
    "hr-shifts",
    "hr-leave",
    "hr-payroll",
    "hr-deductions",
    "hr-training",
    "hr-performance",
    "hr-recruitment",
    "spa",
    "channel",
    "pos",
    "it-infra",
    "integrations",
    "finance",
    "night-audit",
    "surveys",
    "smart-room",
    "agency-operations",
    "lost-found",
    "laundry",
    "laundry-pricelist",
    "minibar",
    "room-rack",
    "res-list",
    "res-card",
    "group-res",
    "forecast",
    "budget",
    "accounting",
    "kvkk",
    "crs",
    "entertainment",
    "cost-control",
    "checkout",
    "sales-marketing",
    "tours",
    "room-inventory-admin",
    "system-admin",
    "dashboard-builder",
)

_OPS_ROLES = (
    (
        "staff_housekeeping",
        "Kat hizmetleri",
        (
            "dashboard",
            "housekeeping",
            "tech-service",
            "laundry",
            "lost-found",
            "room-rack",
            "room-inventory-admin",
        ),
    ),
    (
        "staff_fnb",
        "Yiyecek & içecek",
        (
            "dashboard",
            "fnb-dashboard",
            "fnb-outlets",
            "room-service",
            "pos",
            "recipes",
            "bar-cellar",
            "minibar",
        ),
    ),
    (
        "staff_finance",
        "Muhasebe / finans",
        (
            "dashboard",
            "finance",
            "accounting",
            "cash-desk",
            "night-audit",
            "budget",
            "cost-control",
            "folio",
            "checkout",
        ),
    ),
)


def forwards(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")

    perm_map = {}
    for mid in _ALL_MODULE_IDS:
        code = f"mod.{mid}"
        p, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"description": f"Modül erişimi: {mid}"},
        )
        perm_map[code] = p

    def link_role(role, module_ids):
        for mid in module_ids:
            p = perm_map.get(f"mod.{mid}")
            if p:
                RolePermission.objects.get_or_create(role=role, permission=p)

    for code, name, modules in _OPS_ROLES:
        role, _ = Role.objects.get_or_create(code=code, defaults={"name": name})
        if role.name != name:
            role.name = name
            role.save(update_fields=["name"])
        link_role(role, modules)


def backwards(apps, schema_editor):
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")
    codes = [row[0] for row in _OPS_ROLES]
    RolePermission.objects.filter(role__code__in=codes).delete()
    Role.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0037_groupbookingmember"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
