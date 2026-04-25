"""
Tüm /api/* isteklerinde merkez lisans durumunu doğrular (JWT oturumundan bağımsız).
"""

from django.conf import settings
from django.http import JsonResponse

from .licensing import get_license_state


class LicenseGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        url = (getattr(settings, "LICENSE_SERVER_URL", "") or "").strip()
        key = (getattr(settings, "LICENSE_KEY", "") or "").strip()
        enforce = bool(getattr(settings, "LICENSE_ENFORCE", False))

        if enforce and (not url or not key):
            return JsonResponse(
                {
                    "detail": "Lisans zorunlu: .env içinde LICENSE_SERVER_URL ve LICENSE_KEY ikisi de dolu olmalı.",
                    "code": "license_not_configured",
                },
                status=403,
            )

        if not url or not key:
            return self.get_response(request)

        state = get_license_state()
        if not state.ok:
            return JsonResponse(
                {"detail": state.reason or "Lisans doğrulanamadı.", "code": "license_inactive"},
                status=403,
            )

        return self.get_response(request)
