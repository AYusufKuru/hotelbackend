"""Başarılı API yazma işlemlerini aktivite günlüğüne yazar."""

import json

from hotelcrm.activity_log import describe_api_mutation, extract_hotel_id, log_activity


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/"):
            if request.content_type.startswith("application/json") and request.body:
                try:
                    request._activity_body_cache = json.loads(request.body.decode("utf-8"))  # noqa: SLF001
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            hid = extract_hotel_id(request)
            if hid:
                request._activity_hotel_id = hid  # noqa: SLF001

        response = self.get_response(request)

        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return response

        described = describe_api_mutation(request, response.status_code)
        if described:
            action, module, message = described
            log_activity(
                action=action,
                message=message,
                module=module,
                request=request,
            )

        return response
