"""Stok hareketi kaydı sonrası parti (lot) güncellemeleri."""

from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models.minibar_laundry_inv import InventoryItem, InventoryStockLot, StockMovement
from .stock_lot_service import apply_stock_movement, recompute_item_from_lots


@receiver(post_save, sender=StockMovement)
def _on_stock_movement_saved(sender, instance, created, **kwargs):
    if not created:
        return

    def _run():
        apply_stock_movement(StockMovement.objects.get(pk=instance.pk))

    transaction.on_commit(_run)


@receiver(post_save, sender=InventoryItem)
def _on_inventory_item_initial_lot(sender, instance, created, **kwargs):
    """Yeni ürün kartında başlangıç miktarı varsa tek parti oluştur (hareket olmadan)."""
    if not created:
        return

    def _run():
        qty = Decimal(str(instance.quantity_on_hand or 0))
        if qty <= 0:
            return
        if InventoryStockLot.objects.filter(item_id=instance.pk).exists():
            return
        InventoryStockLot.objects.create(
            hotel=instance.hotel,
            item=instance,
            quantity_initial=qty,
            quantity_remaining=qty,
            unit_cost=instance.unit_cost,
            expiry_date=instance.expiry_date,
            note="Açılış stoğu",
        )
        recompute_item_from_lots(instance.pk)

    transaction.on_commit(_run)
