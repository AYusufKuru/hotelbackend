from rest_framework.viewsets import ModelViewSet

from hotelcrm.activity_log import extract_hotel_id
from hotelcrm.models import HotelRecruitment
from hotelcrm.permissions import HasHotelModule
from hotelcrm.serializers import get_serializer


class HotelRecruitmentScopedViewSet(ModelViewSet):
    """İşe alım panosu: otel kapsamı zorunlu."""

    serializer_class = get_serializer(HotelRecruitment)
    permission_classes = [HasHotelModule]
    required_modules = ("hr-recruitment", "hr")
    queryset = HotelRecruitment.objects.all()

    def get_queryset(self):
        hotel = extract_hotel_id(self.request)
        if not hotel:
            return HotelRecruitment.objects.none()
        return HotelRecruitment.objects.select_related("hotel").filter(hotel_id=hotel)
