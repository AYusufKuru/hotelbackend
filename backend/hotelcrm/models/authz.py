import uuid

from django.conf import settings
from django.db import models


class Role(models.Model):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)

    class Meta:
        db_table = "hotelcrm_role"


class Permission(models.Model):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "hotelcrm_permission"


class UserRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hotelcrm_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_links")

    class Meta:
        db_table = "hotelcrm_userrole"
        unique_together = [("user", "role")]


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permission_links")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_links")

    class Meta:
        db_table = "hotelcrm_rolepermission"
        unique_together = [("role", "permission")]


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    user_label = models.CharField(max_length=128, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hotelcrm_audit_logs",
    )
    module = models.CharField(max_length=64, blank=True)
    action = models.CharField(max_length=32, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        db_table = "hotelcrm_auditlog"
        ordering = ["-occurred_at"]
