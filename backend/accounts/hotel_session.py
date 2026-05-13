from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hotelcrm.models import UserRole
from hotelcrm.rbac import (
    can_assign_tasks,
    can_manage_modules,
    can_manage_users,
    permission_codes_for_user,
    visible_module_ids,
)

User = get_user_model()


class UserLookupView(APIView):
    """GET /api/auth/users/lookup/?hotel=&q= — rol atamak için kullanıcı arama (min 2 karakter)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        hotel_id = request.query_params.get("hotel")
        q = (request.query_params.get("q") or "").strip()
        if not hotel_id or not can_manage_users(request.user, hotel_id):
            return Response({"detail": "Yetkisiz"}, status=403)
        if len(q) < 2:
            return Response([])
        rows = (
            User.objects.filter(username__icontains=q)
            .order_by("username")
            .values("id", "username")[:25]
        )
        return Response(list(rows))


class HotelSessionView(APIView):
    """
    GET /api/auth/session/?hotel=<uuid>
    Seçili otel için menü modülleri, izin bayrakları ve rol listesi.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        hotel_id = request.query_params.get("hotel")
        if not hotel_id:
            return Response({"detail": "hotel sorgu parametresi gerekli."}, status=400)

        u = request.user
        perms = permission_codes_for_user(u, hotel_id)
        vis = visible_module_ids(u, hotel_id)
        roles = [
            {"code": ur.role.code, "name": ur.role.name}
            for ur in UserRole.objects.filter(user=u, hotel_id=hotel_id).select_related("role")
        ]

        return Response(
            {
                "user": {
                    "id": u.pk,
                    "username": u.username,
                    "email": u.email or "",
                    "is_superuser": u.is_superuser,
                    "is_staff": u.is_staff,
                },
                "hotel_id": hotel_id,
                "roles": roles,
                "permissions": sorted(perms),
                "flags": {
                    "can_manage_modules": can_manage_modules(u, hotel_id),
                    "can_manage_users": can_manage_users(u, hotel_id),
                    "can_assign_tasks": can_assign_tasks(u, hotel_id),
                },
                "visible_module_ids": vis,
            },
        )
