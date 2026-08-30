"""StaffMember onboarding + IT/İK ek izinleri ve örnek roller."""

from django.db import migrations, models
import django.db.models.deletion


HR_MODULE_CODES = (
    "mod.hr",
    "mod.hr-dashboard",
    "mod.hr-shifts",
    "mod.hr-leave",
    "mod.hr-payroll",
    "mod.hr-training",
    "mod.hr-performance",
    "mod.hr-recruitment",
)

# (module_id, açıklama) — Permission satırı yoksa oluşturulur
_MODULE_LABELS = (
    ("it-infra", "IT & altyapı"),
    ("hr", "İnsan kaynakları"),
    ("hr-dashboard", "İK Paneli"),
    ("hr-shifts", "Vardiya & Devam"),
    ("hr-leave", "İzin Yönetimi"),
    ("hr-payroll", "Bordro & Maaş"),
    ("hr-training", "Eğitim & Sertifika"),
    ("hr-performance", "Performans & Disiplin"),
    ("hr-recruitment", "İşe Alım"),
)


def _seed_permissions_roles(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")

    for mid, label in _MODULE_LABELS:
        code = f"mod.{mid}"
        Permission.objects.get_or_create(
            code=code,
            defaults={"description": f"Modül erişimi: {label}"},
        )

    defs = [
        ("it.onboarding", "IT personel onboarding kuyruğu ve tamamlama"),
        ("hr.staff.register", "İK yeni personel kaydı (IT onayına düşer)"),
        ("hr.side_register", "İK yarı zamanlı / yan çalışan kayıt yetkisi"),
    ]
    perm_by_code = {}
    for code, desc in defs:
        p, _ = Permission.objects.get_or_create(code=code, defaults={"description": desc})
        perm_by_code[code] = p

    hr_perm = Permission.objects.filter(code="mod.hr").first()
    if hr_perm:
        role_ids = list(
            RolePermission.objects.filter(permission=hr_perm).values_list("role_id", flat=True).distinct(),
        )
        for rid in role_ids:
            RolePermission.objects.get_or_create(
                role_id=rid,
                permission=perm_by_code["hr.staff.register"],
            )

    def link_role(role, codes: list[str]) -> None:
        for c in codes:
            p = Permission.objects.filter(code=c).first()
            if p:
                RolePermission.objects.get_or_create(role=role, permission=p)

    r_it, _ = Role.objects.get_or_create(code="hotel_it", defaults={"name": "Otel IT"})
    link_role(
        r_it,
        [
            "it.onboarding",
            "users.manage",
            "tasks.assign",
            "mod.it-infra",
            "hr.staff.register",
        ]
        + list(HR_MODULE_CODES),
    )

    r_hr, _ = Role.objects.get_or_create(code="hotel_hr", defaults={"name": "Otel İK"})
    link_role(
        r_hr,
        list(HR_MODULE_CODES) + ["hr.staff.register", "tasks.assign"],
    )


def _unseed(apps, schema_editor):
    Permission = apps.get_model("hotelcrm", "Permission")
    Role = apps.get_model("hotelcrm", "Role")
    RolePermission = apps.get_model("hotelcrm", "RolePermission")
    RolePermission.objects.filter(
        permission__code__in=["it.onboarding", "hr.staff.register", "hr.side_register"],
    ).delete()
    Permission.objects.filter(code__in=["it.onboarding", "hr.staff.register", "hr.side_register"]).delete()
    Role.objects.filter(code__in=["hotel_it", "hotel_hr"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("hotelcrm", "0028_minibar_stock_integration"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffmember",
            name="linked_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="staff_member_links",
                to="auth.user",
            ),
        ),
        migrations.AddField(
            model_name="staffmember",
            name="onboarding_status",
            field=models.CharField(
                choices=[("pending_it", "IT onayı bekliyor"), ("active", "Sistemde aktif (IT tamamladı)")],
                db_index=True,
                default="active",
                max_length=16,
            ),
        ),
        migrations.RunPython(_seed_permissions_roles, _unseed),
    ]
