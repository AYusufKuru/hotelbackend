"""Rakip otel arama: Overpass + best-effort Booking fiyat çekme uçları."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .competitor_search import enrich_with_prices, fetch_nearby_hotels
from .models import CompetitorHotel, Hotel


def _parse_decimal(v):
    if v in (None, ""):
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


class CompetitorAutoSearchView(APIView):
    """`POST /api/competitors/auto-search/` — otelin koordinatı etrafında yakındaki otelleri
    OpenStreetMap'ten otomatik bulur, opsiyonel olarak Booking'den fiyat çekmeye çalışır,
    `CompetitorHotel` tablosuna **upsert** eder.

    Body:
      {
        "hotel": "<hotel uuid>",
        "radius_km": 3.0,           # opsiyonel
        "limit": 30,                # opsiyonel
        "fetch_prices": true,       # opsiyonel
        "check_in": "2026-05-01",   # opsiyonel
        "check_out": "2026-05-02"   # opsiyonel
      }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        hotel_id = request.data.get("hotel")
        if not hotel_id:
            return Response({"detail": "hotel zorunlu."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            hotel = Hotel.objects.get(pk=UUID(str(hotel_id)))
        except (Hotel.DoesNotExist, ValueError):
            return Response({"detail": "Otel bulunamadı."}, status=status.HTTP_404_NOT_FOUND)

        if hotel.latitude is None or hotel.longitude is None:
            return Response(
                {
                    "detail": "Otelin enlem/boylam bilgisi yok. Önce 'Otelimin Konumu' ile ayarlayın.",
                    "code": "missing_geo",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        radius_km = float(request.data.get("radius_km") or 3.0)
        limit = int(request.data.get("limit") or 30)
        fetch_prices = bool(request.data.get("fetch_prices", True))
        check_in = request.data.get("check_in")
        check_out = request.data.get("check_out")

        nearby = fetch_nearby_hotels(
            float(hotel.latitude),
            float(hotel.longitude),
            radius_km=radius_km,
            limit=limit,
        )
        if not nearby:
            return Response(
                {
                    "detail": "Yakınlarda otel bulunamadı veya OpenStreetMap geçici olarak yanıt vermedi.",
                    "imported": 0,
                    "updated": 0,
                    "with_price": 0,
                },
                status=status.HTTP_200_OK,
            )

        enriched = enrich_with_prices(
            nearby,
            check_in=check_in if fetch_prices else None,
            check_out=check_out if fetch_prices else None,
            max_lookups=12 if fetch_prices else 0,
            center_lat=float(hotel.latitude),
            center_lng=float(hotel.longitude),
            radius_km=radius_km,
        )

        imported = 0
        updated = 0
        with_price = 0
        sources_used: dict[str, int] = {}
        results: list[dict] = []
        now = datetime.now(timezone.utc)
        for row in enriched:
            price = _parse_decimal(row.get("current_price"))
            obj, created = CompetitorHotel.objects.update_or_create(
                hotel=hotel,
                name=row["name"],
                defaults=dict(
                    address=row.get("address") or "",
                    latitude=Decimal(str(row["latitude"])).quantize(Decimal("0.000001")),
                    longitude=Decimal(str(row["longitude"])).quantize(Decimal("0.000001")),
                    current_price=price if price is not None else None,
                    currency=row.get("currency") or "TRY",
                    source=row.get("source") or "osm",
                    last_observed_at=now if price is not None else None,
                    notes=f"Otomatik içe aktarıldı ({row.get('external_id', '')})".strip(),
                ),
            )
            src = (row.get("source") or "osm")
            sources_used[src] = sources_used.get(src, 0) + 1
            if created:
                imported += 1
            else:
                updated += 1
            if price is not None:
                with_price += 1
            results.append(
                {
                    "id": str(obj.id),
                    "name": obj.name,
                    "current_price": str(obj.current_price) if obj.current_price is not None else None,
                    "address": obj.address,
                    "source": obj.source,
                }
            )

        return Response(
            {
                "imported": imported,
                "updated": updated,
                "with_price": with_price,
                "total": len(enriched),
                "sources": sources_used,
                "amadeus_enabled": "amadeus" in sources_used or bool(_amadeus_keys_present()),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )


def _amadeus_keys_present() -> bool:
    import os
    return bool(os.environ.get("AMADEUS_API_KEY")) and bool(os.environ.get("AMADEUS_API_SECRET"))
