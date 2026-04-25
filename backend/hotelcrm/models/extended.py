import uuid

from django.db import models

from .enums import (
    BanquetEventStatus,
    CommercialContractStatus,
    GLAccountType,
    GroupBookingStatus,
    InvoicePaymentStatus,
    InvoiceType,
    LostFoundStatus,
    PurchaseOrderStatus,
    SalesLeadStage,
)
from .property_guest import Hotel
from .reservation_folio import Reservation


class KbsGuestSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="kbs_submissions")
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="kbs_submissions")
    sent_at = models.DateTimeField()
    national_id = models.CharField(max_length=32, blank=True)
    passport_no = models.CharField(max_length=32, blank=True)
    nationality = models.CharField(max_length=2, blank=True)

    class Meta:
        db_table = "hotelcrm_kbsguestsubmission"


class GroupBooking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="group_bookings")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    leader_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    pax_total = models.PositiveIntegerField()
    rooms_blocked = models.PositiveIntegerField()
    check_in = models.DateField()
    check_out = models.DateField()
    status = models.CharField(max_length=32, choices=GroupBookingStatus.choices)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    board_basis = models.CharField(max_length=8, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "hotelcrm_groupbooking"


class BanquetEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="banquet_events")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    event_type = models.CharField(max_length=64, blank=True)
    hall_name = models.CharField(max_length=128, blank=True)
    event_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    pax = models.PositiveIntegerField()
    status = models.CharField(max_length=32, choices=BanquetEventStatus.choices)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    contact_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "hotelcrm_banquetevent"


class LostFoundItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="lost_found_items")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    location_found = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    found_date = models.DateField()
    status = models.CharField(max_length=32, choices=LostFoundStatus.choices)
    returned_to_guest_name = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "hotelcrm_lostfounditem"


class TravelAgency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="travel_agencies")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    email = models.EmailField(blank=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    agency_status = models.CharField(max_length=16, blank=True)

    class Meta:
        db_table = "hotelcrm_travelagency"


class AgencyContractRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(TravelAgency, on_delete=models.CASCADE, related_name="contract_rates")
    valid_from = models.DateField()
    valid_to = models.DateField()
    room_type_label = models.CharField(max_length=128)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    board_basis = models.CharField(max_length=8, blank=True)

    class Meta:
        db_table = "hotelcrm_agencycontractrate"


class AgencyPromotion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(TravelAgency, on_delete=models.CASCADE, related_name="promotions")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    promo_status = models.CharField(max_length=16, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "hotelcrm_agencypromotion"


class GLAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="gl_accounts")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=32, choices=GLAccountType.choices)
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    class Meta:
        db_table = "hotelcrm_glaccount"
        unique_together = [("hotel", "code")]


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="journal_entries")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    entry_date = models.DateField()
    description = models.CharField(max_length=512)
    debit_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    credit_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    account_code = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hotelcrm_journalentry"


class OperationalInvoice(models.Model):
    """E-fatura / finans modülü (DBML: invoices — Django Invoice reserved değil ama çakışmayı önlemek için prefix)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="operational_invoices")
    invoice_number = models.CharField(max_length=64, unique=True)
    invoice_type = models.CharField(max_length=32, choices=InvoiceType.choices)
    category = models.CharField(max_length=64, blank=True)
    customer_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    invoice_date = models.DateField()
    payment_status = models.CharField(max_length=16, choices=InvoicePaymentStatus.choices)
    tax_id = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hotelcrm_operationalinvoice"


class CommercialContract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="commercial_contracts")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    partner_name = models.CharField(max_length=255)
    contract_kind = models.CharField(max_length=32, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    pricing_terms = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=CommercialContractStatus.choices)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "hotelcrm_commercialcontract"


class SalesLead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="sales_leads")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    account_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2)
    probability_percent = models.PositiveIntegerField(null=True, blank=True)
    stage = models.CharField(max_length=32, choices=SalesLeadStage.choices)
    created_date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "hotelcrm_saleslead"


class MarketingCampaign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="marketing_campaigns")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    target_segment = models.CharField(max_length=64, blank=True)
    accent_color = models.CharField(max_length=16, blank=True)
    campaign_status = models.CharField(max_length=16, blank=True)
    reservation_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "hotelcrm_marketingcampaign"


class TourOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="tour_offers")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    tour_kind = models.CharField(max_length=64, blank=True)
    guest_name = models.CharField(max_length=255)
    tour_date = models.DateField()
    pax = models.PositiveIntegerField()
    status = models.CharField(max_length=32, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_touroffer"


class GuestTransfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="guest_transfers")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    direction = models.CharField(max_length=16, blank=True)
    guest_name = models.CharField(max_length=255)
    location_label = models.CharField(max_length=255, blank=True)
    flight_code = models.CharField(max_length=32, blank=True)
    transfer_date = models.DateField()
    transfer_time = models.TimeField(null=True, blank=True)
    vehicle_label = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = "hotelcrm_guesttransfer"


class Recipe(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="recipes")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2)
    menu_price = models.DecimalField(max_digits=12, decimal_places=2)
    ingredients_text = models.TextField(blank=True)

    class Meta:
        db_table = "hotelcrm_recipe"


class FoodWasteLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="food_waste_logs")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    item_description = models.CharField(max_length=255)
    reason = models.CharField(max_length=128, blank=True)
    loss_amount = models.DecimalField(max_digits=12, decimal_places=2)
    waste_date = models.DateField()

    class Meta:
        db_table = "hotelcrm_foodwastelog"


class DepartmentBudget(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="department_budgets")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    department_name = models.CharField(max_length=255)
    fiscal_year = models.PositiveIntegerField()
    budget_amount = models.DecimalField(max_digits=16, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_departmentbudget"


class EntertainmentActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="entertainment_activities")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location_name = models.CharField(max_length=128, blank=True)
    category = models.CharField(max_length=64, blank=True)
    day_label = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=32, blank=True)
    participant_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "hotelcrm_entertainmentactivity"


class EntertainmentShow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="entertainment_shows")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    show_date_label = models.CharField(max_length=32, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    icon = models.CharField(max_length=8, blank=True)

    class Meta:
        db_table = "hotelcrm_entertainmentshow"


class KvkkConsent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="kvkk_consents")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    guest_name = models.CharField(max_length=255)
    consent_type = models.CharField(max_length=64)
    consent_status = models.CharField(max_length=16)
    record_date = models.DateField()
    recorded_by = models.CharField(max_length=64, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "hotelcrm_kvkkconsent"


class CrsSyncLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chain_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=255)
    from_label = models.CharField(max_length=128, blank=True)
    to_label = models.CharField(max_length=128, blank=True)
    guest_or_ref = models.CharField(max_length=255, blank=True)
    outcome = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_crssynclog"
        ordering = ["-created_at"]


class IntegrationConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True, related_name="integration_connections")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    integration_kind = models.CharField(max_length=64, blank=True)
    connection_status = models.CharField(max_length=16, blank=True)
    api_key_ref = models.CharField(max_length=128, blank=True)
    last_sync_label = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "hotelcrm_integrationconnection"


class IntegrationEventLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    integration = models.ForeignKey(
        IntegrationConnection,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="event_logs",
    )
    service_code = models.CharField(max_length=64, blank=True)
    event_type = models.CharField(max_length=128, blank=True)
    outcome = models.CharField(max_length=32, blank=True)
    meta = models.TextField(blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_integrationeventlog"
        ordering = ["-occurred_at"]


class PurchaseOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="purchase_orders")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    item_description = models.CharField(max_length=512)
    supplier_name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    order_date = models.DateField()
    status = models.CharField(max_length=32, choices=PurchaseOrderStatus.choices)

    class Meta:
        db_table = "hotelcrm_purchaseorder"


class GuestFeedbackEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="guest_feedback_entries")
    guest_name = models.CharField(max_length=255)
    room_number = models.CharField(max_length=16, blank=True)
    score = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    category = models.CharField(max_length=64, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_guestfeedbackentry"
        ordering = ["-submitted_at"]


class ChannelManagerSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.OneToOneField(Hotel, on_delete=models.CASCADE, related_name="channel_manager_settings")
    rate_standard = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rate_deluxe = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rate_suite = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rate_family = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stop_sale_single = models.BooleanField(default=False)
    stop_sale_double = models.BooleanField(default=False)
    stop_sale_triple = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hotelcrm_channelmanagersettings"
