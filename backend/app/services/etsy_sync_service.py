import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_token, encrypt_token
from app.models.catalog_listing import CatalogListing
from app.models.enums import EtsyAccountStatus, EtsySyncStatus, SaleChannel
from app.models.etsy_account import EtsyAccount
from app.models.etsy_listing_image import EtsyListingImage
from app.models.etsy_listing_sync import EtsyListingSync
from app.models.sale import Sale
from app.schemas.sale import SaleCreate, SaleLineInput
from app.services import etsy_service, image_service
from app.services.catalog_service import attach_derived_availability
from app.services.sales_service import create_sale
from app.services.storefront_service import public_available_quantity


def get_active_account_or_error(db: Session) -> EtsyAccount:
    account = db.query(EtsyAccount).filter(EtsyAccount.status == EtsyAccountStatus.active).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active Etsy shop is connected.")
    return account


def _access_token_for(db: Session, account: EtsyAccount) -> str:
    stored = decrypt_token(account.refresh_token_encrypted)
    try:
        tokens = etsy_service.refresh_access_token(stored)
        # Etsy hands back a refresh token on every refresh. Persist it when it
        # has changed, or the stored one eventually hits its 90-day limit and
        # the shop silently needs reconnecting.
        rotated = tokens.get("refresh_token")
        if rotated and rotated != stored:
            account.refresh_token_encrypted = encrypt_token(rotated)
            db.commit()
        return tokens["access_token"]
    except etsy_service.EtsyAuthError:
        account.status = EtsyAccountStatus.needs_reauth
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Etsy access for {account.shop_name or account.shop_id} has expired. Reconnect the shop.",
        )


def shipping_profile_options(db: Session) -> list[dict]:
    """The connected shop's shipping profiles as {id, label} for a dropdown."""
    account = get_active_account_or_error(db)
    profiles = etsy_service.get_shop_shipping_profiles(account.shop_id, _access_token_for(db, account))
    return [
        {
            "id": str(profile.get("shipping_profile_id")),
            "label": profile.get("title") or f"Profile {profile.get('shipping_profile_id')}",
        }
        for profile in profiles
        if profile.get("shipping_profile_id") is not None
    ]


def return_policy_options(db: Session) -> list[dict]:
    account = get_active_account_or_error(db)
    policies = etsy_service.get_shop_return_policies(account.shop_id, _access_token_for(db, account))
    options = []
    for policy in policies:
        policy_id = policy.get("return_policy_id")
        if policy_id is None:
            continue
        # Etsy's return policies have no title — describe them by their terms
        # so two policies on one shop are tellable apart.
        if policy.get("accepts_returns"):
            label = f"Accepts returns within {policy.get('return_deadline', '?')} days"
            if policy.get("accepts_exchanges"):
                label += ", exchanges allowed"
        else:
            label = "No returns or exchanges"
        options.append({"id": str(policy_id), "label": label})
    return options


# Etsy's seller taxonomy is thousands of nodes and effectively static, so it's
# fetched once and held in memory rather than re-pulled for every keystroke in
# the listing form's search box.
_TAXONOMY_CACHE: dict = {"fetched_at": 0.0, "options": []}
_TAXONOMY_TTL_SECONDS = 24 * 60 * 60


def _flatten_taxonomy(nodes: list[dict], prefix: str = "") -> list[dict]:
    """Depth-first flatten into {id, label} with the full category path.

    The path is what makes a node pickable: "Beads" alone appears in several
    branches, where "Craft Supplies & Tools > Beads > Glass Beads" doesn't.
    """
    flattened: list[dict] = []
    for node in nodes:
        name = node.get("name") or ""
        label = f"{prefix} > {name}" if prefix else name
        node_id = node.get("id")
        if node_id is not None:
            flattened.append({"id": str(node_id), "label": label})
        children = node.get("children") or []
        if children:
            flattened.extend(_flatten_taxonomy(children, label))
    return flattened


def taxonomy_options(db: Session, search: str | None = None, limit: int = 50) -> list[dict]:
    """Searchable Etsy taxonomy categories as {id, label}.

    Searching server-side against the cached tree keeps the response small —
    handing the browser every node would be megabytes.
    """
    now = time.time()
    if not _TAXONOMY_CACHE["options"] or now - _TAXONOMY_CACHE["fetched_at"] > _TAXONOMY_TTL_SECONDS:
        account = get_active_account_or_error(db)
        nodes = etsy_service.get_seller_taxonomy_nodes(_access_token_for(db, account))
        _TAXONOMY_CACHE["options"] = _flatten_taxonomy(nodes)
        _TAXONOMY_CACHE["fetched_at"] = now

    options = _TAXONOMY_CACHE["options"]
    if search:
        needle = _search_stem(search)
        # Rank a match on the node's own name above one buried in its path, so
        # searching "beads" offers the Beads categories before everything
        # filed under them — a search for "cabochons" matches every child of
        # "Beads, Gems & Cabochons" too, and the one you meant should be top.
        def sort_key(option: dict) -> tuple[int, int, int, str]:
            leaf = option["label"].rsplit(" > ", 1)[-1].lower()
            return (
                # The category's own name starting with what was typed is the
                # strongest signal, then merely containing it, then a match
                # only somewhere in its ancestry.
                0 if leaf.startswith(needle) else 1,
                0 if needle in leaf else 1,
                # Shortest *leaf* among equals: searching "cabochons" should
                # offer "Cabochons" before "Beads, Gems & Cabochons", which
                # ranking by full path length gets backwards.
                len(leaf),
                option["label"],
            )

        options = sorted(
            (option for option in options if needle in option["label"].lower()), key=sort_key
        )
    return options[:limit]


def _search_stem(search: str) -> str:
    """Drop a trailing plural so "beads" also finds "Beaded" and "Beading".

    Matched against the whole path, which lets "jewelry findings" work, and
    crudely de-pluralized because Etsy's category names are inconsistent
    about it — a reviewer typing the word they'd use shouldn't have to guess
    Etsy's. Left alone for short words, where chopping a letter does more
    harm than good.
    """
    needle = search.strip().lower()
    if len(needle) > 3 and needle.endswith("s"):
        return needle[:-1]
    return needle


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

    price = float(listing.price) if listing.price is not None else 0
    # The shop's own product code, which Etsy carries on the listing's
    # inventory — it's what makes an incoming Etsy order identifiable as this
    # product rather than something matched by title.
    product_sku = listing.product.sku if listing.product else None

    try:
        if sync_row.etsy_listing_id is None:
            result = etsy_service.create_draft_listing(
                account.shop_id,
                access_token,
                {
                    "quantity": quantity,
                    "title": listing.title,
                    "description": listing.listing_description or listing.short_description or listing.title,
                    "price": price,
                    "who_made": sync_row.who_made,
                    "when_made": sync_row.when_made,
                    "taxonomy_id": sync_row.taxonomy_id,
                    "shipping_profile_id": sync_row.shipping_profile_id,
                    "return_policy_id": sync_row.return_policy_id,
                    "is_supply": sync_row.is_supply,
                },
            )
            sync_row.etsy_listing_id = str(result["listing_id"])

        # Inventory is updated on every push, including straight after a
        # create: Etsy keeps the SKU on the inventory rather than the listing,
        # so a create alone would leave the listing without one until some
        # later push happened to come along.
        offering = {"price": price, "quantity": quantity, "is_enabled": True}
        inventory_product: dict = {"offerings": [offering]}
        if product_sku:
            inventory_product["sku"] = product_sku
        etsy_service.update_listing_inventory(
            account.shop_id,
            sync_row.etsy_listing_id,
            access_token,
            {"products": [inventory_product]},
        )

        # Photos, which a listing can't go active without. Part of the push
        # rather than its own step because uploading costs nothing and the
        # listing is useless without them — activation is the separate,
        # deliberate act.
        image_result = sync_listing_images(db, sync_row, access_token)

        if sync_row.etsy_state is None:
            # createDraftListing's state. Recorded so the UI can tell a draft
            # from a live listing without asking Etsy.
            sync_row.etsy_state = "draft"
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


def sync_listing_images(db: Session, sync_row: EtsyListingSync, access_token: str) -> dict:
    """Make Etsy's images for this listing match the product's photos.

    Etsy fixes an image's rank at upload and offers no way to reorder an
    existing one, so there are only two honest options: leave the order wrong,
    or re-upload. This compares what was last sent against what the product
    now has, and when they differ — a photo added, removed, replaced, or
    reordered — deletes Etsy's copies and uploads the current set in order.

    When they match, it does nothing at all, which is the common case: a push
    that only changes price or quantity doesn't touch the images.
    """
    if sync_row.etsy_listing_id is None:
        return {"uploaded": 0, "deleted": 0, "unchanged": 0}

    product_id = sync_row.catalog_listing.product_id
    desired = image_service.list_images(db, product_id)

    recorded = (
        db.query(EtsyListingImage)
        .filter(EtsyListingImage.etsy_listing_sync_id == sync_row.id)
        .order_by(EtsyListingImage.rank)
        .all()
    )

    # Compared on checksum rather than id, so replacing a photo with a
    # different one counts as a change even at the same position.
    if [row.checksum for row in recorded] == [image.checksum for image in desired]:
        return {"uploaded": 0, "deleted": 0, "unchanged": len(recorded)}

    deleted = 0
    for row in recorded:
        etsy_service.delete_listing_image(
            sync_row.etsy_shop_id, sync_row.etsy_listing_id, row.etsy_image_id, access_token
        )
        db.delete(row)
        deleted += 1
    db.flush()

    uploaded = 0
    for position, image in enumerate(desired[: image_service.MAX_IMAGES_PER_PRODUCT], start=1):
        result = etsy_service.upload_listing_image(
            sync_row.etsy_shop_id,
            sync_row.etsy_listing_id,
            access_token,
            data=image_service.read_image_bytes(image),
            filename=image.original_filename or f"{image.id}.jpg",
            content_type=image.content_type,
            rank=position,
            alt_text=image.alt_text,
        )
        db.add(
            EtsyListingImage(
                etsy_listing_sync_id=sync_row.id,
                product_image_id=image.id,
                etsy_image_id=str(result.get("listing_image_id") or result.get("image_id") or ""),
                rank=position,
                checksum=image.checksum,
            )
        )
        uploaded += 1

    db.flush()
    return {"uploaded": uploaded, "deleted": deleted, "unchanged": 0}


def activate_listing(db: Session, catalog_listing_id: uuid.UUID) -> EtsyListingSync:
    """Make a pushed listing public on Etsy.

    Deliberately separate from pushing, and never automatic. Going active is
    what puts the listing in front of buyers and is what Etsy charges its
    per-listing fee for — not a side effect a price sync should be able to
    trigger.
    """
    sync_row = (
        db.query(EtsyListingSync)
        .filter(EtsyListingSync.catalog_listing_id == catalog_listing_id)
        .first()
    )
    if sync_row is None or sync_row.etsy_listing_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This listing hasn't been pushed to Etsy yet, so there's nothing to activate.",
        )

    image_count = (
        db.query(EtsyListingImage).filter(EtsyListingImage.etsy_listing_sync_id == sync_row.id).count()
    )
    if image_count == 0:
        # Etsy refuses this anyway; saying so here is clearer than relaying
        # its error, and explains what to do about it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Etsy won't show a listing with no photos. Add at least one photo to the product "
                "and push again, then activate."
            ),
        )

    account = get_active_account_or_error(db)
    access_token = _access_token_for(db, account)

    try:
        result = etsy_service.update_listing(
            sync_row.etsy_shop_id, sync_row.etsy_listing_id, access_token, {"state": "active"}
        )
    except HTTPException as exc:
        sync_row.last_error = str(exc.detail)
        db.commit()
        raise

    sync_row.etsy_state = result.get("state") or "active"
    sync_row.last_error = None
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
