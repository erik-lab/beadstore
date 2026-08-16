import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import InventoryAdjustmentType, InventoryUnitStatus
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_unit import InventoryUnit
from app.models.product import Product
from app.models.sale import Sale, SaleLine
from app.schemas.sale import SaleCreate

# The demand-side counterpart to services/piece_service.py's component
# consumption: decrements inventory via InventoryAdjustment rows (oldest
# stock first) rather than a new ad-hoc mechanism, so the audit trail and
# "why did this unit's quantity change" story stay consistent across both
# consumption paths.


def create_sale(db: Session, payload: SaleCreate) -> Sale:
    # Resolve products and reserve FIFO unit queues for every line *before*
    # mutating anything, aggregating demand per product first — two lines
    # for the same product must be checked against combined demand, not
    # each independently against the same starting stock.
    demand: dict[uuid.UUID, float] = {}
    for line in payload.lines:
        demand[line.product_id] = demand.get(line.product_id, 0.0) + float(line.quantity)

    products: dict[uuid.UUID, Product] = {}
    unit_queues: dict[uuid.UUID, list[InventoryUnit]] = {}
    for product_id, needed in demand.items():
        product = db.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found")
        products[product_id] = product

        units = (
            db.query(InventoryUnit)
            .filter(InventoryUnit.product_id == product_id, InventoryUnit.status == InventoryUnitStatus.available)
            .order_by(InventoryUnit.received_date, InventoryUnit.created_at)
            .all()
        )
        available = sum(float(u.quantity) for u in units)
        if available < needed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'Only {available} available of "{product.name}", cannot sell {needed}',
            )
        unit_queues[product_id] = units

    sale = Sale(
        channel=payload.channel,
        external_order_id=payload.external_order_id,
        sale_date=payload.sale_date or date.today(),
        notes=payload.notes,
    )
    db.add(sale)
    db.flush()

    for line in payload.lines:
        to_consume = float(line.quantity)
        for unit in unit_queues[line.product_id]:
            if to_consume <= 0:
                break
            available_in_unit = float(unit.quantity)
            if available_in_unit <= 0:
                continue
            take = min(to_consume, available_in_unit)
            db.add(
                InventoryAdjustment(
                    inventory_unit_id=unit.id,
                    adjustment_type=InventoryAdjustmentType.sold,
                    quantity_delta=-take,
                    reason=f"Sale {sale.id}",
                )
            )
            unit.quantity = available_in_unit - take
            if unit.quantity <= 0:
                unit.status = InventoryUnitStatus.depleted
            to_consume -= take

        db.add(
            SaleLine(
                sale_id=sale.id,
                catalog_listing_id=line.catalog_listing_id,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
        )

    db.commit()
    db.refresh(sale)
    return sale


def list_sales(db: Session, limit: int = 50, offset: int = 0) -> list[Sale]:
    return db.query(Sale).order_by(Sale.sale_date.desc(), Sale.created_at.desc()).offset(offset).limit(limit).all()


def get_sale_or_404(db: Session, sale_id: uuid.UUID) -> Sale:
    sale = db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    return sale
