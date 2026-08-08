from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import InventoryAdjustmentType, InventoryUnitStatus, PieceCostSource, PieceCreationStatus, UnitType
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_unit import InventoryUnit
from app.models.piece_creation import PieceComponent, PieceCreation
from app.models.product import Product
from app.schemas.piece_creation import PieceCreationCreate


def create_piece(db: Session, payload: PieceCreationCreate) -> PieceCreation:
    product = db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Resolve and validate every component up front, before mutating
    # anything — a shortfall on the last line shouldn't leave earlier lines
    # already decremented.
    resolved: list[tuple[InventoryUnit, float]] = []
    estimated_cost = 0.0
    all_costs_known = True
    for component in payload.components:
        unit = db.get(InventoryUnit, component.inventory_unit_id)
        if unit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory unit {component.inventory_unit_id} not found",
            )
        available = float(unit.quantity)
        if component.quantity_used > available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only {available} available of \"{unit.product_name or unit.unresolved_description}\", "
                f"cannot use {component.quantity_used}",
            )
        resolved.append((unit, component.quantity_used))
        if unit.cost_amount is not None:
            estimated_cost += float(unit.cost_amount) * component.quantity_used
        else:
            all_costs_known = False

    if payload.creation_cost is not None:
        creation_cost = payload.creation_cost
        cost_source = PieceCostSource.manual
    elif resolved and all_costs_known:
        creation_cost = round(estimated_cost, 2)
        cost_source = PieceCostSource.estimated_from_components
    else:
        creation_cost = None
        cost_source = PieceCostSource.manual

    piece_creation = PieceCreation(
        product_id=product.id,
        created_date=payload.created_date or date.today(),
        quantity_produced=payload.quantity_produced,
        creation_cost=creation_cost,
        cost_source=cost_source,
        notes=payload.notes,
    )
    db.add(piece_creation)
    db.flush()

    for unit, quantity_used in resolved:
        db.add(
            InventoryAdjustment(
                inventory_unit_id=unit.id,
                adjustment_type=InventoryAdjustmentType.consumed_in_piece,
                quantity_delta=-quantity_used,
                reason=f"Used in creating {product.name}",
            )
        )
        unit.quantity = float(unit.quantity) - quantity_used
        if unit.quantity <= 0 and unit.status == InventoryUnitStatus.available:
            unit.status = InventoryUnitStatus.depleted
        db.add(
            PieceComponent(
                piece_creation_id=piece_creation.id,
                inventory_unit_id=unit.id,
                quantity_used=quantity_used,
                unit_cost_at_use=unit.cost_amount,
            )
        )

    resulting_unit = InventoryUnit(
        product_id=product.id,
        quantity=payload.quantity_produced,
        unit_type=UnitType.piece,
        status=InventoryUnitStatus.available,
        received_date=piece_creation.created_date,
        cost_amount=creation_cost,
        notes=f"Created via piece creation {piece_creation.id}",
    )
    db.add(resulting_unit)
    db.flush()
    piece_creation.resulting_inventory_unit_id = resulting_unit.id

    db.commit()
    db.refresh(piece_creation)
    return piece_creation


def cancel_piece_creation(db: Session, piece_creation: PieceCreation) -> PieceCreation:
    if piece_creation.status == PieceCreationStatus.cancelled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This piece creation is already cancelled")

    resulting = piece_creation.resulting_inventory_unit
    if resulting is not None and (
        float(resulting.quantity) != float(piece_creation.quantity_produced)
        or resulting.status != InventoryUnitStatus.available
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can't cancel — the resulting inventory has already been sold, moved, or adjusted. "
            "Use a manual inventory adjustment instead.",
        )

    for component in piece_creation.components:
        unit = component.inventory_unit
        db.add(
            InventoryAdjustment(
                inventory_unit_id=unit.id,
                adjustment_type=InventoryAdjustmentType.consumed_in_piece,
                quantity_delta=float(component.quantity_used),
                reason=f"Reversed piece creation for {piece_creation.product_name}",
            )
        )
        unit.quantity = float(unit.quantity) + float(component.quantity_used)
        if unit.status == InventoryUnitStatus.depleted and float(unit.quantity) > 0:
            unit.status = InventoryUnitStatus.available

    if resulting is not None:
        resulting.quantity = 0
        resulting.status = InventoryUnitStatus.archived

    piece_creation.status = PieceCreationStatus.cancelled
    db.commit()
    db.refresh(piece_creation)
    return piece_creation
