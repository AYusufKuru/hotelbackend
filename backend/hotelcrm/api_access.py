"""API kaynak → modül eşlemesi ve otel queryset kapsamı."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from hotelcrm.activity_log import extract_hotel_id

# Ortak kümeler — bir kayda birden fazla ekran dokunur; herhangi biri yeter
_FO = (
    "front-office",
    "res-list",
    "res-card",
    "new-reservation",
    "reservations-tape",
    "checkout",
    "room-rack",
    "folio",
    "group-res",
    "kbs",
    "guest-inform",
    "night-audit",
)
_HK = ("housekeeping", "tech-service", "laundry", "lost-found", "room-rack", "room-inventory-admin")
_FNB = (
    "fnb-dashboard",
    "fnb-outlets",
    "room-service",
    "pos",
    "recipes",
    "bar-cellar",
    "minibar",
)
_HR = (
    "hr",
    "hr-dashboard",
    "hr-shifts",
    "hr-leave",
    "hr-payroll",
    "hr-deductions",
    "hr-training",
    "hr-performance",
    "hr-recruitment",
)
_FIN = ("finance", "accounting", "cash-desk", "night-audit", "budget", "cost-control", "folio", "checkout")
_CRM = ("crm", "loyalty", "guest-inform", "kbs", "surveys")

# model._meta.model_name → gereken modül id'leri (boş = otel üyeliği yeterli)
MODEL_MODULES: dict[str, tuple[str, ...]] = {
    "room": _FO + _HK + ("minibar", "spa"),
    "roomtype": _FO + ("room-inventory-admin", "channel", "crs", "revenue"),
    "channel": _FO + ("channel", "crs"),
    "guest": _FO + _CRM,
    "reservation": _FO,
    "reservationoccupant": _FO,
    "folio": _FO + _FIN,
    "folioline": _FO + _FIN,
    "payment": _FO + _FIN,
    "cashtransaction": _FIN + ("front-office",),
    "department": _HR + ("housekeeping", "it-infra"),
    "staffmember": _HR + ("it-infra", "system-admin"),
    "staffabsencereport": _HR,
    "hotelrecruitment": ("hr-recruitment", "hr"),
    "operationaltask": (),
    "notification": (),
    "menucategory": _FNB,
    "menuitem": _FNB,
    "restaurantorder": _FNB,
    "restaurantorderline": _FNB,
    "spaservice": ("spa",),
    "spaappointment": ("spa",),
    "minibarproduct": ("minibar",),
    "minibarcharge": ("minibar", "folio", "checkout"),
    "minibarchargeline": ("minibar", "folio", "checkout"),
    "laundrypricelistitem": ("laundry", "laundry-pricelist"),
    "laundryorder": ("laundry",),
    "laundryorderline": ("laundry",),
    "inventoryitem": ("stock", "purchasing", "recipes", "minibar", "pos", "cost-control"),
    "stockmovement": ("stock", "purchasing", "cost-control"),
    "inventorystocklot": ("stock", "purchasing"),
    "stockcountsession": ("stock",),
    "stockcountline": ("stock",),
    "kbsguestsubmission": ("kbs", "front-office"),
    "groupbooking": ("group-res",) + _FO[:4],
    "groupbookingmember": ("group-res",) + _FO[:4],
    "banquetevent": ("banquet", "meetings"),
    "lostfounditem": ("lost-found", "housekeeping"),
    "travelagency": ("agency-operations", "sales-marketing", "tours"),
    "agencycontractrate": ("agency-operations",),
    "agencypromotion": ("agency-operations",),
    "glaccount": _FIN,
    "journalentry": _FIN,
    "operationalinvoice": _FIN + ("purchasing",),
    "commercialcontract": ("agency-operations", "sales-marketing"),
    "saleslead": ("sales-marketing",),
    "marketingcampaign": ("sales-marketing",),
    "touroffer": ("tours", "agency-operations"),
    "guesttransfer": _FO + ("tours",),
    "recipe": ("recipes",) + _FNB[:3],
    "foodwastelog": ("cost-control", "recipes", "fnb-dashboard"),
    "departmentbudget": ("budget", "finance"),
    "entertainmentactivity": ("entertainment",),
    "entertainmentshow": ("entertainment",),
    "kvkkconsent": ("kvkk", "crm"),
    "crssynclog": ("crs", "channel"),
    "integrationconnection": ("integrations", "it-infra"),
    "integrationeventlog": ("integrations", "it-infra"),
    "purchaseorder": ("purchasing", "stock", "cost-control"),
    "guestfeedbackentry": ("surveys", "crm"),
    "hotelsurveysmssettings": ("surveys",),
    "surveyinvitation": ("surveys",),
    "channelmanagersettings": ("channel", "crs"),
    "competitorhotel": ("global-vision", "revenue", "ai-strategy"),
    "fixedasset": ("accounting", "finance", "cost-control"),
    "businesspartner": ("accounting", "purchasing", "finance"),
    "italarmwebhook": ("it-infra",),
    "italertlog": ("it-infra",),
    "itmetricsample": ("it-infra",),
}

# hotel FK'si olmayan çocuk kayıtlar
_CHILD_HOTEL_FILTER: dict[str, str] = {
    "folio": "reservation__hotel_id",
    "folioline": "folio__reservation__hotel_id",
    "reservationoccupant": "reservation__hotel_id",
    "payment": "reservation__hotel_id",
    "restaurantorderline": "order__hotel_id",
    "minibarchargeline": "charge__hotel_id",
    "laundryorderline": "laundry_order__hotel_id",
    "stockcountline": "session__hotel_id",
    "groupbookingmember": "group_booking__hotel_id",
    "agencycontractrate": "agency__hotel_id",
    "agencypromotion": "agency__hotel_id",
    "itmetricsample": "integration__hotel_id",
    "integrationeventlog": "integration__hotel_id",
}

# Özel APIView'lar
ENDPOINT_MODULES: dict[str, tuple[str, ...]] = {
    "night-audit": ("night-audit",),
    "surveys": ("surveys",),
    "it-infra": ("it-infra",),
    "global-vision": ("global-vision", "revenue", "ai-strategy"),
    "assistant": ("dashboard", "ai-strategy"),
}


def modules_for_model(model) -> tuple[str, ...]:
    return MODEL_MODULES.get(model._meta.model_name, ())


def scope_queryset_to_hotel(model, hotel_id: str, *, superuser: bool = False):
    name = model._meta.model_name
    qs = model.objects.all()
    if name == "crssynclog":
        return qs if superuser else qs.none()
    path = _CHILD_HOTEL_FILTER.get(name)
    if path:
        return qs.filter(**{path: hotel_id})
    field_names = {f.name for f in model._meta.fields}
    if "hotel" in field_names:
        return qs.filter(hotel_id=hotel_id)
    if name == "hotel":
        return qs.filter(pk=hotel_id)
    return qs.none()


def assert_payload_hotel_matches_request(request, serializer) -> None:
    hotel_id = extract_hotel_id(request)
    if not hotel_id or "hotel" not in getattr(serializer, "validated_data", {}):
        return
    raw = serializer.validated_data.get("hotel")
    obj_id = str(getattr(raw, "pk", raw))
    if obj_id != str(hotel_id):
        raise PermissionDenied("Kayıt başka bir otele yazılamaz.")
