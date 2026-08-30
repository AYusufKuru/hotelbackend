"""Stok partileri (lot): girişte parti oluşturma, çıkışta SKT'ye göre FIFO tüketim."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models.minibar_laundry_inv import (
    InventoryItem,
    InventoryStockLot,
    StockMovement,
    StockMovementType,
)

logger = logging.getLogger(__name__)

_MAX_SK_ORDER = Value(date(9999, 12, 31), output_field=models.DateField())


def recompute_item_from_lots(item_id) -> None:
    """Parti kalan toplamından quantity_on_hand, ortalama maliyet ve en yakın SKT güncellenir."""
    item = InventoryItem.objects.get(pk=item_id)
    lots = InventoryStockLot.objects.filter(item_id=item_id, quantity_remaining__gt=0)
    agg = lots.aggregate(t=Sum("quantity_remaining"))
    total = agg.get("t")
    if total is None:
        total = Decimal("0")
    else:
        total = Decimal(str(total))

    weighted_num = Decimal("0")
    den = Decimal("0")
    earliest: date | None = None
    for lot in lots.only("quantity_remaining", "unit_cost", "expiry_date"):
        q = Decimal(str(lot.quantity_remaining))
        if q <= 0:
            continue
        c = lot.unit_cost
        if c is not None:
            weighted_num += q * Decimal(str(c))
            den += q
        if lot.expiry_date:
            if earliest is None or lot.expiry_date < earliest:
                earliest = lot.expiry_date

    avg_cost = (weighted_num / den) if den > 0 else item.unit_cost

    InventoryItem.objects.filter(pk=item_id).update(
        quantity_on_hand=total,
        unit_cost=avg_cost,
        expiry_date=earliest,
        last_restocked_at=timezone.now(),
    )


def fifo_consume(item: InventoryItem, need: Decimal) -> list[tuple[Decimal, Decimal | None, date | None]]:
    """SKT'si yakın partilerden düş; (miktar, birim maliyet, skt) dilimlerini döndür (transfer birleştirme)."""
    if need <= 0:
        return []
    consumed: list[tuple[Decimal, Decimal | None, date | None]] = []
    remaining = need

    qs = (
        InventoryStockLot.objects.select_for_update()
        .filter(item=item, quantity_remaining__gt=0)
        .order_by(Coalesce("expiry_date", _MAX_SK_ORDER), "received_at", "id")
    )
    for lot in qs:
        if remaining <= 0:
            break
        rem = Decimal(str(lot.quantity_remaining))
        take = min(rem, remaining)
        if take <= 0:
            continue
        consumed.append((take, lot.unit_cost, lot.expiry_date))
        new_rem = rem - take
        InventoryStockLot.objects.filter(pk=lot.pk).update(quantity_remaining=new_rem)
        remaining -= take

    if remaining > 0:
        logger.warning(
            "lot fifo eksik: item=%s ihtiyac_kalan=%s; operasyon devam etti",
            item.id,
            remaining,
        )
    return consumed


def find_transfer_target_item(hotel_id, source: InventoryItem, to_wh_raw: str) -> InventoryItem | None:
    to_w = (to_wh_raw or "").strip()
    if not to_w:
        return None
    sku = (source.sku or "").strip()
    name = (source.name or "").strip()
    qs = InventoryItem.objects.filter(hotel_id=hotel_id, is_archived=False)
    if sku:
        hit = qs.filter(sku=sku, warehouse__iexact=to_w).first()
        if hit:
            return hit
    return qs.filter(name__iexact=name, warehouse__iexact=to_w).first()


def _add_incoming_lot(mv: StockMovement) -> None:
    qty = Decimal(str(mv.quantity))
    InventoryStockLot.objects.create(
        hotel=mv.item.hotel,
        item=mv.item,
        quantity_initial=qty,
        quantity_remaining=qty,
        unit_cost=mv.unit_cost,
        expiry_date=mv.expiry_date,
        source_movement=mv,
        note="",
    )


@transaction.atomic
def apply_stock_movement(mv: StockMovement) -> None:
    """Yeni kaydedilen stok hareketine göre partileri ve ürün özetini güncelle."""
    item = InventoryItem.objects.select_for_update().get(pk=mv.item_id)
    mt = mv.movement_type
    qty = Decimal(str(mv.quantity))

    if mt in (StockMovementType.IN, StockMovementType.RETURN):
        _add_incoming_lot(mv)
        recompute_item_from_lots(item.id)
        return

    if mt in (StockMovementType.OUT, StockMovementType.WASTE):
        fifo_consume(item, qty)
        recompute_item_from_lots(item.id)
        return

    if mt == StockMovementType.TRANSFER:
        consumed = fifo_consume(item, qty)
        recompute_item_from_lots(item.id)
        target = find_transfer_target_item(item.hotel_id, item, mv.to_warehouse or "")
        if target and target.id != item.id:
            total = sum((c[0] for c in consumed), Decimal("0"))
            if total > 0:
                weighted = sum((c[0] * (c[1] or Decimal("0"))) for c in consumed)
                avg_cost = weighted / total
                expiries = [c[2] for c in consumed if c[2]]
                earliest_exp = min(expiries) if expiries else None
                InventoryStockLot.objects.create(
                    hotel=target.hotel,
                    item=target,
                    quantity_initial=total,
                    quantity_remaining=total,
                    unit_cost=avg_cost,
                    expiry_date=earliest_exp,
                    source_movement=mv,
                    note="Depo transferi",
                )
                recompute_item_from_lots(target.id)
        return

    if mt == StockMovementType.COUNT:
        reason = (mv.reason or "").lower()
        if "eksiği" in reason or "eksik" in reason:
            fifo_consume(item, qty)
        else:
            unit = mv.unit_cost if mv.unit_cost is not None else item.unit_cost
            InventoryStockLot.objects.create(
                hotel=item.hotel,
                item=item,
                quantity_initial=qty,
                quantity_remaining=qty,
                unit_cost=unit,
                expiry_date=None,
                source_movement=mv,
                note="Sayım fazlası",
            )
        recompute_item_from_lots(item.id)
        return

    recompute_item_from_lots(item.id)
