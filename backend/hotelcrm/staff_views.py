"""Personel (StaffMember) — otel kapsamı ve İK → IT onboarding kuralları."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from hotelcrm.activity_log import extract_hotel_id
from hotelcrm.models import StaffMember
from hotelcrm.models.enums import StaffOnboardingStatus
from hotelcrm.permissions import HasHotelModule
from hotelcrm.rbac import can_direct_manage_staff_record, can_list_hotel_staff, permission_codes_for_user
from hotelcrm.serializers import get_serializer


def _employment_type(hr_profile) -> str | None:
    if not isinstance(hr_profile, dict):
        return None
    job = hr_profile.get("job")
    if not isinstance(job, dict):
        return None
    et = job.get("employmentType")
    return et if isinstance(et, str) else None


class StaffMemberScopedViewSet(ModelViewSet):
    """
    Liste ve yazma işlemleri için `?hotel=<uuid>` gerekir (veya POST gövdesinde `hotel`).

    - `hr.staff.register`: yeni kayıt IT onay kuyruğuna düşer (`onboarding_status=pending_it`).
    - `hr.side_register`: çalışma tipi «yarı zamanlı» (yan/yarı zamanlı) kayıt.
    - `it.onboarding` veya `users.manage` vb.: doğrudan tamamlanmış kayıt / onboarding kapatma.
    """

    serializer_class = get_serializer(StaffMember)
    permission_classes = [HasHotelModule]
    queryset = StaffMember.objects.all()
    required_modules = (
        "hr",
        "hr-dashboard",
        "hr-shifts",
        "hr-leave",
        "hr-payroll",
        "hr-deductions",
        "hr-training",
        "hr-performance",
        "hr-recruitment",
        "it-infra",
        "system-admin",
    )

    def get_queryset(self):
        hotel = extract_hotel_id(self.request)
        if not hotel:
            return StaffMember.objects.none()
        user = self.request.user
        if not can_list_hotel_staff(user, hotel):
            return StaffMember.objects.none()
        return (
            StaffMember.objects.filter(hotel_id=hotel)
            .select_related("department", "linked_user")
            .order_by("full_name")
        )

    def list(self, request, *args, **kwargs):
        if not request.query_params.get("hotel"):
            return Response({"detail": "hotel sorgu parametresi gerekli."}, status=400)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        hotel_raw = request.query_params.get("hotel") or (
            request.data.get("hotel") if isinstance(request.data, dict) else None
        )
        if not hotel_raw:
            return Response({"detail": "hotel sorgu parametresi veya gövdede hotel gerekli."}, status=400)
        hotel_id = str(hotel_raw)
        if not can_list_hotel_staff(request.user, hotel_id):
            raise PermissionDenied("Personel kaydı için yetkiniz yok.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        hotel_field = serializer.validated_data.get("hotel")
        hotel_id = str(getattr(hotel_field, "pk", hotel_field))
        if not can_list_hotel_staff(self.request.user, hotel_id):
            raise PermissionDenied("Personel kaydı için yetkiniz yok.")

        perms = permission_codes_for_user(self.request.user, hotel_id)
        direct = can_direct_manage_staff_record(self.request.user, hotel_id)
        hr_reg = "hr.staff.register" in perms
        if not direct and not hr_reg:
            raise PermissionDenied("Yeni personel oluşturma yetkisi yok.")

        hr_profile = serializer.validated_data.get("hr_profile") or {}
        emp_type = _employment_type(hr_profile)
        if emp_type == "parttime":
            if not direct and "hr.side_register" not in perms:
                raise PermissionDenied(
                    "Yarı zamanlı (yan çalışan) kayıt için IT tarafından «Yan çalışan kayıt» izni gerekir.",
                )

        if direct:
            serializer.validated_data.setdefault(
                "onboarding_status",
                StaffOnboardingStatus.ACTIVE,
            )
        else:
            serializer.validated_data["onboarding_status"] = StaffOnboardingStatus.PENDING_IT
            serializer.validated_data["linked_user"] = None

        serializer.save()

    def perform_update(self, serializer):
        inst = serializer.instance
        assert inst is not None
        hotel_id = str(inst.hotel_id)
        if not can_list_hotel_staff(self.request.user, hotel_id):
            raise PermissionDenied("Personel güncelleme için yetkiniz yok.")

        perms = permission_codes_for_user(self.request.user, hotel_id)
        direct = can_direct_manage_staff_record(self.request.user, hotel_id)
        hr_reg = "hr.staff.register" in perms

        if not direct:
            serializer.validated_data.pop("onboarding_status", None)
            serializer.validated_data.pop("linked_user", None)
            hr_profile = serializer.validated_data.get("hr_profile")
            if hr_profile is not None:
                base_prof = inst.hr_profile if isinstance(inst.hr_profile, dict) else {}
                merged = {**base_prof}
                if isinstance(hr_profile, dict):
                    merged.update(hr_profile)
                prev_et = _employment_type(base_prof)
                if _employment_type(merged) == "parttime" and prev_et != "parttime":
                    if "hr.side_register" not in perms and not direct:
                        raise PermissionDenied(
                            "Yarı zamanlı (yan çalışan) olarak işaretlemek için IT onaylı yan kayıt izni gerekir.",
                        )

            can_hr_edit = (
                direct
                or hr_reg
                or "mod.hr" in perms
                or any(p.startswith("mod.hr") for p in perms)
            )
            if not direct and not can_hr_edit:
                raise PermissionDenied("Güncelleme yetkisi yok.")

        serializer.save()

    def perform_destroy(self, instance):
        hotel_id = str(instance.hotel_id)
        perms = permission_codes_for_user(self.request.user, hotel_id)
        if can_direct_manage_staff_record(self.request.user, hotel_id):
            instance.delete()
            return
        if "hr.staff.register" in perms and instance.onboarding_status == StaffOnboardingStatus.PENDING_IT:
            instance.delete()
            return
        raise PermissionDenied("Personel kaydını silme yetkisi yok.")
