"""DRF izinleri: JWT yetmez; otel üyeliği + modül yetkisi gerekir."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from hotelcrm.activity_log import extract_hotel_id
from hotelcrm.rbac import user_belongs_to_hotel, user_can_use_modules


class HasHotelModule(BasePermission):
    """
    Authenticated kullanıcı, istekteki otelin üyesi olmalı.
    `view.required_modules` doluysa menüde o modüllerden en az biri görünür olmalı.
    `view.allow_without_hotel=True` ise yalnızca giriş yeter (otel listesi).
    """

    message = "Bu işlem için yetkiniz yok."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if getattr(view, "allow_without_hotel", False):
            return True

        hotel_id = extract_hotel_id(request)
        if not hotel_id:
            self.message = "Otel bilgisi gerekli (X-Hotel-Id veya ?hotel=)."
            return False
        if not user_belongs_to_hotel(user, hotel_id):
            self.message = "Bu otele erişiminiz yok."
            return False
        modules = tuple(getattr(view, "required_modules", ()) or ())
        if not user_can_use_modules(user, hotel_id, modules):
            self.message = "Bu işlem için modül yetkiniz yok."
            return False
        return True
