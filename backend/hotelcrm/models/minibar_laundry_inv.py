import uuid

from django.db import models

from .enums import LaundryOrderStatus
from .property_guest import Hotel, Room
from .reservation_folio import Reservation


class MinibarProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="minibar_products")
    display_code = models.CharField(max_length=32, blank=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_minibarproduct"


class MinibarCharge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="minibar_charges")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="minibar_charges")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="minibar_charges",
    )
    charge_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    billed_to_folio = models.BooleanField(default=False)

    class Meta:
        db_table = "hotelcrm_minibarcharge"


class MinibarChargeLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    charge = models.ForeignKey(MinibarCharge, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(MinibarProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name="lines")
    inventory_item = models.ForeignKey(
        "hotelcrm.InventoryItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="minibar_charge_lines",
        help_text="Mini bar fiş satırı stok kalemiyle eşleşir; eski ürün kataloğu opsiyoneldir.",
    )
    name_snapshot = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_minibarchargeline"


class LaundryPricelistItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="laundry_pricelist_items")
    name = models.CharField(max_length=128)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_laundrypricelistitem"


class LaundryOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="laundry_orders")
    display_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="laundry_orders")
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="laundry_orders",
    )
    guest_name = models.CharField(max_length=255)
    order_date = models.DateField()
    ordered_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=LaundryOrderStatus.choices)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_laundryorder"


class LaundryOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    laundry_order = models.ForeignKey(LaundryOrder, on_delete=models.CASCADE, related_name="lines")
    pricelist_item = models.ForeignKey(
        LaundryPricelistItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_lines",
    )
    name_snapshot = models.CharField(max_length=128)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "hotelcrm_laundryorderline"


class InventoryUsageArea(models.TextChoices):
    """Stok kaleminin satış/POS tarafında kullanılıp kullanılmayacağı."""

    STOCK_ONLY = "stock_only", "Sadece stok"
    RESTAURANT = "restaurant", "Restoran (POS menüsü)"
    MINIBAR = "minibar", "Mini Bar (oda tüketim katalogu)"


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="inventory_items")
    display_code = models.CharField(max_length=32, blank=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=64, blank=True)
    warehouse = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Depo / lokasyon (örn. Ana depo, Mutfak, HK)",
    )
    usage_area = models.CharField(
        max_length=24,
        choices=InventoryUsageArea.choices,
        default=InventoryUsageArea.STOCK_ONLY,
        help_text=(
            "Restoran seçilirse ürün Stok tanımından POS menüsünde listelenir. "
            "Mini Bar seçilirse mini bar katalogunda listelenir ve oda tüketiminde stoktan düşer."
        ),
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Restoran satış fiyatı. Boşsa POS’da birim maliyet gösterilir.",
    )
    unit = models.CharField(max_length=32, blank=True)
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=2)
    min_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    max_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Yeniden sipariş tavanı; boşsa min_quantity * 4 kabul edilir.",
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sku = models.CharField(max_length=64, blank=True, default="")
    barcode = models.CharField(max_length=64, blank=True, default="")
    supplier_name = models.CharField(max_length=128, blank=True, default="")
    location_in_warehouse = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Raf / lokasyon (örn. R3-Ü2)",
    )
    expiry_date = models.DateField(null=True, blank=True)
    last_restocked_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    is_archived = models.BooleanField(default=False)

    class Meta:
        db_table = "hotelcrm_inventoryitem"


class StockMovementType(models.TextChoices):
    IN = "in", "Giriş"
    OUT = "out", "Çıkış"
    TRANSFER = "transfer", "Transfer"
    COUNT = "count", "Sayım düzeltmesi"
    WASTE = "waste", "Fire / zayi"
    RETURN = "return", "Tedarikçi iadesi"


class StockMovement(models.Model):
    """Tüm stok hareketlerinin (giriş, çıkış, transfer, sayım, fire, iade) izlenebilir kaydı."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    movement_type = models.CharField(
        max_length=16,
        choices=StockMovementType.choices,
        default=StockMovementType.IN,
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Pozitif miktar; yön movement_type ile belirlenir.",
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    from_warehouse = models.CharField(max_length=64, blank=True, default="")
    to_warehouse = models.CharField(max_length=64, blank=True, default="")
    reason = models.CharField(max_length=128, blank=True, default="")
    reference_no = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Satın alma emri no, fatura no, vb.",
    )
    staff_name = models.CharField(max_length=128, blank=True, default="")
    business_date = models.DateField()
    note = models.TextField(blank=True, default="")
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text="Giriş / iade parti SKT (isteğe bağlı).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_stockmovement"
        ordering = ["-created_at"]


class InventoryStockLot(models.Model):
    """Ürün kartı altında parti/lot: her mal kabulde ayrı alış fiyatı ve tüketim tarihi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="inventory_stock_lots")
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="stock_lots",
    )
    quantity_initial = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_remaining = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default="")
    source_movement = models.ForeignKey(
        "StockMovement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_lots",
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_inventorystocklot"
        ordering = ["received_at", "id"]


class StockCountSession(models.Model):
    """Sayım oturumu — başlık. Satırlar StockCountLine."""

    STATUS_CHOICES = (
        ("open", "Açık"),
        ("closed", "Tamamlandı"),
        ("cancelled", "İptal"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name="stock_count_sessions",
    )
    display_code = models.CharField(max_length=32, blank=True, default="")
    title = models.CharField(max_length=128, default="Stok sayımı")
    warehouse = models.CharField(max_length=64, blank=True, default="")
    started_on = models.DateField()
    closed_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="open")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hotelcrm_stockcountsession"
        ordering = ["-started_on", "-created_at"]


class StockCountLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        StockCountSession,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="count_lines",
    )
    expected_qty = models.DecimalField(max_digits=12, decimal_places=2)
    counted_qty = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        db_table = "hotelcrm_stockcountline"
