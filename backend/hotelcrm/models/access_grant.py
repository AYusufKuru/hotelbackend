from django.conf import settings
from django.db import models


class UserModuleGrant(models.Model):
    """Kullanıcı + otel bazında görünür modül (rol şablonundan bağımsız daraltma)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="module_grants",
    )
    hotel = models.ForeignKey(
        "hotelcrm.Hotel",
        on_delete=models.CASCADE,
        related_name="user_module_grants",
    )
    module_id = models.CharField(max_length=64)

    class Meta:
        db_table = "hotelcrm_usermodulegrant"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "hotel", "module_id"],
                name="hotelcrm_usermodulegrant_uniq",
            ),
        ]
