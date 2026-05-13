"""
Çevredeki rakip otelleri otomatik bulan servis.

Üç kaynak (sırayla denenir):

1. **Overpass API (OpenStreetMap)** — `tourism=hotel` POI'leri (otel listesi + koordinat).
   Her zaman çalışır, anahtar gerekmez. Fiyat YOK.

2. **Amadeus Self-Service Hotel Search** — `.env` içinde `AMADEUS_API_KEY` ve
   `AMADEUS_API_SECRET` varsa kullanılır. Booking, Expedia gibi birden fazla tedarikçiden
   gerçek fiyat çeker. **Önerilen** yol; ücretsiz tier ayda 1000 istek.

3. **Best-effort Booking.com HTML parse** — anti-bot (Cloudflare) yüzünden çoğu zaman
   başarısız olur. Sadece elimizde başka kaynak yoksa son çare olarak denenir; başarısız
   olursa fiyat boş kalır ve kullanıcı manuel günceller veya "Booking'te aç" linkini
   kullanır.

Notlar:
- Aramanın merkezi otelin kendi `latitude`/`longitude`'udur; otel koordinatı yoksa
  istemciye 400 döner.
- Booking'i sürekli toplu scrape etmek TOS ihlalidir; bu kod sadece 12 otele kadar
  best-effort denemesi yapar.
"""
from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


@dataclass
class NearbyHotel:
    name: str
    latitude: float
    longitude: float
    address: str
    osm_id: str
    stars: int | None = None


def fetch_nearby_hotels(
    lat: float,
    lng: float,
    radius_km: float = 3.0,
    limit: int = 30,
    timeout: float = 25.0,
) -> list[NearbyHotel]:
    """OpenStreetMap Overpass API üzerinden `tourism=hotel` POI'lerini getirir."""
    radius_m = int(min(15, max(0.3, radius_km)) * 1000)
    query = f"""
    [out:json][timeout:20];
    (
      node["tourism"="hotel"](around:{radius_m},{lat},{lng});
      way["tourism"="hotel"](around:{radius_m},{lat},{lng});
    );
    out center {limit};
    """
    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("Overpass çağrısı başarısız: %s", e)
        return []

    hotels: list[NearbyHotel] = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        if el.get("type") == "node":
            la = el.get("lat")
            ln = el.get("lon")
        else:
            center = el.get("center") or {}
            la = center.get("lat")
            ln = center.get("lon")
        if la is None or ln is None:
            continue
        addr_parts = [
            tags.get("addr:street", ""),
            tags.get("addr:housenumber", ""),
            tags.get("addr:city", ""),
            tags.get("addr:district", ""),
        ]
        address = ", ".join([p for p in addr_parts if p]).strip(", ")
        stars_raw = tags.get("stars") or tags.get("rating")
        stars: int | None = None
        if stars_raw:
            m = re.search(r"\d", str(stars_raw))
            if m:
                try:
                    s = int(m.group(0))
                    if 1 <= s <= 5:
                        stars = s
                except ValueError:
                    pass
        hotels.append(
            NearbyHotel(
                name=name,
                latitude=float(la),
                longitude=float(ln),
                address=address,
                osm_id=f"{el.get('type','?')}/{el.get('id','?')}",
                stars=stars,
            )
        )
        if len(hotels) >= limit:
            break
    return hotels


_PRICE_PATTERNS = (
    re.compile(r'data-testid="price-and-discounted-price"[^>]*>\s*([^<]+)<'),
    re.compile(r'class="[^"]*prco-valign-middle-helper[^"]*">\s*([^<]+)<'),
    re.compile(r'"priceDisplayValue"\s*:\s*"([^"]+)"'),
    re.compile(r'"price"\s*:\s*"([^"]+)"'),
)


def _parse_price_from_html(html: str) -> Decimal | None:
    """Booking sayfasındaki ilk gözlenen fiyatı çıkarır. Bulamazsa None."""
    for pat in _PRICE_PATTERNS:
        m = pat.search(html)
        if not m:
            continue
        raw = m.group(1)
        cleaned = re.sub(r"[^\d,\.]", "", raw)
        if not cleaned:
            continue
        cleaned = cleaned.replace(".", "").replace(",", ".") if cleaned.count(",") == 1 else cleaned.replace(",", "")
        try:
            v = Decimal(cleaned)
            if 50 < v < 500_000:
                return v
        except (InvalidOperation, ValueError):
            continue
    return None


def best_effort_booking_price(
    hotel_name: str,
    check_in: str | None = None,
    check_out: str | None = None,
    timeout: float = 12.0,
) -> Decimal | None:
    """Booking.com search sayfasından ilk fiyatı parse etmeye çalışır.
    Başarısız olursa None döner — bilinçli bir best-effort'dur."""
    params: list[tuple[str, str]] = [
        ("ss", hotel_name),
        ("lang", "tr"),
        ("selected_currency", "TRY"),
    ]
    if check_in:
        params.append(("checkin", check_in))
    if check_out:
        params.append(("checkout", check_out))
    try:
        resp = requests.get(
            "https://www.booking.com/searchresults.html",
            params=params,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.5",
            },
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            logger.debug("Booking arama %s döndürdü: %s", resp.status_code, hotel_name)
            return None
        return _parse_price_from_html(resp.text)
    except Exception as e:  # noqa: BLE001
        logger.debug("Booking fetch başarısız (%s): %s", hotel_name, e)
        return None


_AMADEUS_TOKEN_CACHE: dict = {"token": None, "expires_at": 0.0}


def _amadeus_credentials() -> tuple[str | None, str | None, str]:
    key = os.environ.get("AMADEUS_API_KEY") or ""
    secret = os.environ.get("AMADEUS_API_SECRET") or ""
    base = os.environ.get("AMADEUS_BASE_URL", "https://test.api.amadeus.com").rstrip("/")
    return (key or None), (secret or None), base


def _amadeus_token() -> str | None:
    key, secret, base = _amadeus_credentials()
    if not key or not secret:
        return None
    now = time.time()
    cached = _AMADEUS_TOKEN_CACHE
    if cached["token"] and cached["expires_at"] - 30 > now:
        return cached["token"]
    try:
        resp = requests.post(
            f"{base}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": key,
                "client_secret": secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
        token = body.get("access_token")
        ttl = float(body.get("expires_in", 1700))
        cached["token"] = token
        cached["expires_at"] = now + ttl
        return token
    except Exception as e:  # noqa: BLE001
        logger.warning("Amadeus token alınamadı: %s", e)
        return None


def amadeus_prices_by_geo(
    lat: float,
    lng: float,
    radius_km: float = 3.0,
    check_in: str | None = None,
    check_out: str | None = None,
    timeout: float = 12.0,
) -> dict[str, dict]:
    """`{ lower(name): {price, currency, hotel_id} }` döndürür. Anahtar yoksa boş dict."""
    token = _amadeus_token()
    if not token:
        return {}
    _, _, base = _amadeus_credentials()
    headers = {"Authorization": f"Bearer {token}"}

    out: dict[str, dict] = {}
    try:
        list_resp = requests.get(
            f"{base}/v1/reference-data/locations/hotels/by-geocode",
            params={
                "latitude": f"{lat:.6f}",
                "longitude": f"{lng:.6f}",
                "radius": int(min(20, max(1, radius_km))),
                "radiusUnit": "KM",
                "hotelSource": "ALL",
            },
            headers=headers,
            timeout=timeout,
        )
        if list_resp.status_code != 200:
            logger.info("Amadeus geocode %s: %s", list_resp.status_code, list_resp.text[:200])
            return {}
        hotel_ids = [h.get("hotelId") for h in list_resp.json().get("data", []) if h.get("hotelId")][:30]
        if not hotel_ids:
            return {}

        for chunk_start in range(0, len(hotel_ids), 8):
            chunk = hotel_ids[chunk_start : chunk_start + 8]
            params = {"hotelIds": ",".join(chunk), "currency": "TRY", "bestRateOnly": "true"}
            if check_in:
                params["checkInDate"] = check_in
            if check_out:
                params["checkOutDate"] = check_out
            try:
                offers_resp = requests.get(
                    f"{base}/v3/shopping/hotel-offers",
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
                if offers_resp.status_code != 200:
                    continue
                for item in offers_resp.json().get("data", []):
                    h = item.get("hotel") or {}
                    name = (h.get("name") or "").strip().lower()
                    offers = item.get("offers") or []
                    if not name or not offers:
                        continue
                    price_obj = offers[0].get("price") or {}
                    total = price_obj.get("total") or price_obj.get("base")
                    cur = price_obj.get("currency") or "TRY"
                    if not total:
                        continue
                    out[name] = {
                        "price": Decimal(str(total)),
                        "currency": cur,
                        "hotel_id": h.get("hotelId"),
                    }
            except Exception as e:  # noqa: BLE001
                logger.debug("Amadeus offers chunk hata: %s", e)
                continue
    except Exception as e:  # noqa: BLE001
        logger.warning("Amadeus geocode hata: %s", e)
        return {}

    return out


def enrich_with_prices(
    hotels: Iterable[NearbyHotel],
    check_in: str | None = None,
    check_out: str | None = None,
    max_lookups: int = 12,
    center_lat: float | None = None,
    center_lng: float | None = None,
    radius_km: float = 3.0,
) -> list[dict]:
    """Otel listesine en güvenilir kaynaktan fiyat ekle.

    Sıra:
      1) Amadeus toplu geocode (varsa); isim eşleşmesi ile her otel için fiyat.
      2) Eşleşmeyen otellerin ilk `max_lookups` tanesi için best-effort Booking.
      3) Hiçbiri çalışmazsa fiyat None.
    """
    hotels = list(hotels)
    amadeus_map: dict[str, dict] = {}
    if center_lat is not None and center_lng is not None:
        amadeus_map = amadeus_prices_by_geo(
            center_lat, center_lng,
            radius_km=radius_km,
            check_in=check_in, check_out=check_out,
        )

    out: list[dict] = []
    booking_attempts = 0
    for h in hotels:
        price: Decimal | None = None
        currency = "TRY"
        source = "osm"
        ama_match = amadeus_map.get(h.name.lower().strip())
        if not ama_match:
            for k, v in amadeus_map.items():
                if h.name.lower().strip()[:8] and h.name.lower().strip()[:8] in k:
                    ama_match = v
                    break
        if ama_match:
            price = ama_match["price"]
            currency = ama_match.get("currency") or "TRY"
            source = "amadeus"
        elif booking_attempts < max_lookups:
            booking_attempts += 1
            try:
                p = best_effort_booking_price(h.name, check_in=check_in, check_out=check_out)
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                price = p
                source = "booking"

        out.append(
            {
                "name": h.name,
                "address": h.address,
                "latitude": h.latitude,
                "longitude": h.longitude,
                "current_price": str(price) if price is not None else None,
                "currency": currency,
                "source": source,
                "external_id": h.osm_id,
            }
        )
    return out
