import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_token
from app.models.catalog_listing import CatalogListing
from app.models.enums import EtsyAccountStatus, EtsySyncStatus, SaleChannel
from app.models.etsy_account import EtsyAccount
from app.models.etsy_listing_sync import EtsyListingSync
from app.models.sale import Sale
from app.schemas.sale import SaleCreate, SaleLineInput
from app.services import etsy_service
from app.services.catalog_service import attach_derived_availability
from app.services.sales_service import create_sale
from app.services.storefront_service import public_available_quantity


def get_active_account_or_error(db: Session) -> EtsyAccount:
    account = db.query(EtsyAccount).filter(EtsyAccount.status == EtsyAccountStatus.active).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active Etsy shop is connected.")
    return account


def _access_token_for(db: Session, account: EtsyAccount) -> str:
    try:
        return etsy_service.refresh_access_token(decrypt_token(account.refresh_token_encrypted))
    except etsy_service.EtsyAuthError:
        account.status = EtsyAccountStatus.needs_reauth
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Etsy access for {account.shop_name or account.shop_id} has expired. Reconnect the shop.",
        )


def get_or_create_sync_row(db: Session, catalog_listing_id: uuid.UUID, shop_id: str) -> EtsyListingSync:
    row = db.query(EtsyListingSync).filter(EtsyListingSync.catalog_listing_id == catalog_listing_id).first()
    if row is None:
        row = EtsyListingSync(catalog_listing_id=catalog_listing_id, etsy_shop_id=shop_id)
        db.add(row)
        db.flush()
    return row


def push_listing(db: Session, catalog_listing_id: uuid.UUID, overrides: dict | None = None) -> EtsyListingSync:
    """Push one catalog listing to Etsy — creates a draft listing the first
    time, updates price/quantity on subsequent pushes. `overrides` can set
    the Etsy-only fields (taxonomy_id, shipping_profile_id, ...) that have
    no home on CatalogListing itself.
    """
    listing = db.get(CatalogListing, catalog_listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog listing not found")

    account = get_active_account_or_error(db)
    sync_row = get_or_create_sync_row(db, catalog_listing_id, account.shop_id)
    for field, value in (overrides or {}).items():
        if hasattr(sync_row, field) and value is not None:
            setattr(sync_row, field, value)

    missing = [
        f
        for f in ("taxonomy_id", "shipping_profile_id", "return_policy_id", "who_made", "when_made")
        if getattr(sync_row, f) is None
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required Etsy listing fields before this can be pushed: {', '.join(missing)}",
        )

    access_token = _access_token_for(db, account)
    attach_derived_availability(db, listing)
    quantity = public_available_quantity(listing) or 0

    try:
        if sync_row.etsy_listing_id is None:
            result = etsy_service.create_draft_listing(
                account.shop_id,
                access_token,
                {
                    "quantity": quantity,
                    "title": listing.title,
                    "description": listing.listing_description or listing.short_description or listing.title,
                    "price": float(listing.price) if listing.price is not None else 0,
                    "who_made": sync_row.who_made,
                    "when_made": sync_row.when_made,
                    "taxonomy_id": sync_row.taxonomy_id,
                    "shipping_profile_id": sync_row.shipping_profile_id,
                    "return_policy_id": sync_row.return_policy_id,
                    "is_supply": sync_row.is_supply,
                },
            )
            sync_row.etsy_listing_id = str(result["listing_id"])
        else:
            etsy_service.update_listing_inventory(
                account.shop_id,
                sync_row.etsy_listing_id,
                access_token,
                {
                    "products": [
                        {
                            "offerings": [
                                {"price": float(listing.price) if listing.price is not None else 0, "quantity": quantity, "is_enabled": True}
                            ]
                        }
                    ]
                },
            )
        sync_row.sync_status = EtsySyncStatus.synced
        sync_row.last_synced_at = datetime.now(timezone.utc)
        sync_row.last_error = None
    except HTTPException as exc:
        sync_row.sync_status = EtsySyncStatus.error
        sync_row.last_error = str(exc.detail)
        db.commit()
        raise

    db.commit()
    db.refresh(sync_row)
    return sync_row


def pull_receipts(db: Session) -> dict:
    """Reconcile paid Etsy orders into Sale rows. Dedupes against Sale.external_order_id,
    so this is safe to call repeatedly — from a webhook, a polling schedule,
    or a manual "sync now" click, in any combination, without double-counting.
    """
    account = get_active_account_or_error(db)
    access_token = _access_token_for(db, account)

    already_recorded = {
        s.external_order_id
        for s in db.query(Sale.external_order_id).filter(Sale.channel == SaleChannel.etsy).all()
        if s.external_order_id
    }

    receipts = etsy_service.get_shop_receipts(account.shop_id, access_token)
    created, skipped_unmapped, skipped_duplicate = 0, 0, 0

    for receipt in receipts.get("results", []):
        receipt_id = str(receipt["receipt_id"])
        if receipt_id in already_recorded:
            skipped_duplicate += 1
            continue

        lines: list[SaleLineInput] = []
        for txn in receipt.get("transactions", []):
            sync_row = (
                db.query(EtsyListingSync)
                .filter(
                    EtsyListingSync.etsy_listing_id == str(txn["listing_id"]),
                    EtsyListingSync.etsy_shop_id == account.shop_id,
                )
                .first()
            )
            if sync_row is None:
                continue
            price = txn.get("price", {})
            unit_price = price.get("amount", 0) / price.get("divisor", 100) if price else None
            lines.append(
                SaleLineInput(
                    product_id=sync_row.catalog_listing.product_id,
                    catalog_listing_id=sync_row.catalog_listing_id,
                    quantity=txn.get("quantity", 1),
                    unit_price=unit_price,
                )
            )

        if not lines:
            skipped_unmapped += 1
            continue

        create_sale(
            db,
            SaleCreate(channel=SaleChannel.etsy, external_order_id=receipt_id, lines=lines),
        )
        created += 1

    return {"created": created, "skipped_unmapped": skipped_unmapped, "skipped_duplicate": skipped_duplicate}
