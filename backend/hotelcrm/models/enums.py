"""DBML şemasındaki Enum karşılıkları (TextChoices)."""
from django.db import models


class RoomOccupancyStatus(models.TextChoices):
    VACANT = "vacant", "Vacant"
    OCCUPIED = "occupied", "Occupied"
    OUT_OF_ORDER = "out_of_order", "Out of order"


class HousekeepingCleanStatus(models.TextChoices):
    CLEAN = "clean", "Clean"
    DIRTY = "dirty", "Dirty"


class LoyaltyTier(models.TextChoices):
    NONE = "None", "None"
    SILVER = "Silver", "Silver"
    GOLD = "Gold", "Gold"
    PLATINUM = "Platinum", "Platinum"


class BoardBasis(models.TextChoices):
    BB = "BB", "BB"
    HB = "HB", "HB"
    AI = "AI", "AI"


class ReservationStatus(models.TextChoices):
    UPCOMING = "upcoming", "Upcoming"
    CHECKED_IN = "checked_in", "Checked in"
    CHECKED_OUT = "checked_out", "Checked out"
    CANCELLED = "cancelled", "Cancelled"


class FolioLineType(models.TextChoices):
    ACCOMMODATION = "accommodation", "Accommodation"
    EXTRA = "extra", "Extra"
    TAX = "tax", "Tax"
    PAYMENT = "payment", "Payment"


class CashFlowType(models.TextChoices):
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CREDIT_CARD = "credit_card", "Credit card"
    EFT = "eft", "EFT"
    OTHER = "other", "Other"


class StaffStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ON_LEAVE = "on_leave", "On leave"
    INACTIVE = "inactive", "Inactive"


class TaskCategory(models.TextChoices):
    HOUSEKEEPING = "housekeeping", "Housekeeping"
    TECHNICAL = "technical", "Technical"


class TaskStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    DONE = "done", "Done"


class RestaurantOrderStatus(models.TextChoices):
    PREPARING = "preparing", "Preparing"
    READY = "ready", "Ready"
    COMPLETED = "completed", "Completed"


class SpaAppointmentStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class LaundryOrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    WASHING = "washing", "Washing"
    READY = "ready", "Ready"
    DELIVERED = "delivered", "Delivered"


class GroupBookingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class BanquetEventStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class LostFoundStatus(models.TextChoices):
    WAITING = "waiting", "Waiting"
    RETURNED = "returned", "Returned"


class GLAccountType(models.TextChoices):
    ASSET = "asset", "Asset"
    LIABILITY = "liability", "Liability"
    REVENUE = "revenue", "Revenue"
    EXPENSE = "expense", "Expense"
    EQUITY = "equity", "Equity"


class InvoiceType(models.TextChoices):
    SALE = "sale", "Sale"
    PURCHASE = "purchase", "Purchase"
    REFUND = "refund", "Refund"


class InvoicePaymentStatus(models.TextChoices):
    UNPAID = "unpaid", "Unpaid"
    PAID = "paid", "Paid"


class CommercialContractStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVIEW = "review", "Review"
    EXPIRING = "expiring", "Expiring"
    ENDED = "ended", "Ended"


class SalesLeadStage(models.TextChoices):
    NEW_LEAD = "new_lead", "New lead"
    MEETING = "meeting", "Meeting"
    PROPOSAL = "proposal", "Proposal"
    WON = "won", "Won"
    LOST = "lost", "Lost"


class PurchaseOrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVAL = "approval", "Approval"
    IN_TRANSIT = "in_transit", "In transit"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"
