# Patti Back Office MVP — Refinement Pass Report (Prompt 4)

Scope: usability/clarity refinement ahead of Patti's first business walkthrough. No new major
features, no scope expansion, no Render deployment work (per instructions).

---

## 1. Summary of Changes Made

**Human-readable names everywhere an ID or "Linked product" used to show (Goal 1).** The backend
now resolves `product_name`, `product_sku`, `vendor_name`, and `location_name` directly on
inventory units, purchase order lines, and receipt lines via SQLAlchemy relationships + computed
properties — no separate frontend lookups required. A shared `describeItem()` helper renders
`"Product Name (SKU: X)"` when linked, or `"Unresolved: <description>"` when not, and is now used
consistently across the inventory list, inventory detail, PO detail (both expected lines and each
receipt's lines), the receive/quick-receive result screens, and both discrepancy/inventory-on-hand
operational views.

**Product detail now shows full operational history (Goal 2).** Two new backend endpoints —
`GET /products/{id}/purchase-order-lines` and `GET /products/{id}/receipt-lines` — return every
order line and receipt line tied to a product, enriched with the parent order's vendor and date.
The product detail page gained two new sections, **Supplier Order Lines** and **Receiving
Activity**, alongside the existing Inventory Units and Catalog Listings sections (which also now
show vendor/location per unit). One page now answers "what do we have, where is it, how did it
get here, which vendor/order."

**Unresolved-item visibility and a real correctness fix (Goal 3).** The Items Needing Product
Match view now shows vendor, received date, and a link to the originating supplier order, not just
the free-text description and quantity. More importantly: this page was previously calling the
generic inventory-unit PATCH endpoint to "resolve" an item, which updated the inventory unit but
**left the originating receipt line stuck showing the old unresolved description forever** — a
real bug, not a display issue. It now calls the dedicated `/receipt-lines/{id}/resolve` endpoint
when a receipt line exists, which updates both records together, matching the requirement that
"the linked receipt line and inventory unit should display the product name" after resolving.

**Reconciliation clarity on receiving screens (Goal 4).** Both the "receive against order" and
"quick receive" result screens previously showed only aggregate counts by status
(`{"matched": 1, "shortage": 1}`). They now show a real per-line table: item, received
quantity/unit, reconciliation status badge, and discrepancy notes. The purchase order detail
page's Receipts section, which previously only showed a received date and a line count, now
expands every receipt into its own table of lines with the same detail — so a user can see exactly
what happened on each of potentially several partial receipts against one order.

**Label review (Goal 5).** Confirmed no raw enum values or technical terms leak into the UI:
`lot` remains excluded from every unit-type dropdown (only present internally in the shared
TypeScript union type, never rendered), `StatusBadge` continues to map `submitted` → "Ordered" and
snake_case values to Title Case everywhere, and the new sections added in this pass ("Supplier
Order Lines," "Receiving Activity," "Match to Product") follow the same vendor/product/vendor/
supplier-order/discrepancy vocabulary as the rest of the app.

**Scope boundaries (Goal 6):** confirmed unchanged — no storefront, customer orders, payments,
shipping, image upload, barcode, AI/OCR, or role complexity was added. No Render work was done.

---

## 2. Files Changed

**Backend:**
- `app/models/inventory_unit.py` — added `product`/`vendor`/`location`/`receipt_line`
  relationships and `product_name`/`product_sku`/`vendor_name`/`location_name`/
  `receipt_received_date` properties.
- `app/models/purchase_order.py` — added `vendor` relationship + `vendor_name` on `PurchaseOrder`;
  added `product` relationship + `product_name`/`product_sku`/`order_date`/`vendor_name`
  properties on `PurchaseOrderLine`.
- `app/models/receipt.py` — added `purchase_order` relationship on `Receipt`; added `product`/
  `location` relationships + `product_name`/`product_sku`/`location_name`/`purchase_order_id`/
  `received_date`/`vendor_name` properties on `ReceiptLine`.
- `app/schemas/inventory_unit.py`, `app/schemas/purchase_order.py`, `app/schemas/receiving.py` —
  added the corresponding optional fields to `InventoryUnitRead`, `PurchaseOrderLineRead`,
  `PurchaseOrderRead`, `ReceiptLineRead`.
- `app/routers/products.py` — added `GET /products/{id}/purchase-order-lines` and
  `GET /products/{id}/receipt-lines`.
- `backend/tests/test_products.py` — two new tests (name resolution on inventory list; product
  detail history endpoints).
- `backend/tests/test_retroactive_receiving.py` — extended the resolve test to assert
  `product_name` populates on both the receipt line and its inventory unit after resolving.

**Frontend:**
- `src/lib/types.ts` — added the new optional fields to `InventoryUnit`, `PurchaseOrderLine`,
  `PurchaseOrder`, `ReceiptLine`; added the shared `describeItem()` helper.
- `src/pages/inventoryUnits/InventoryUnitsListPage.tsx`, `InventoryUnitDetailPage.tsx` — real
  names, vendor/location columns, links to product/vendor/order.
- `src/pages/purchaseOrders/PurchaseOrderDetailPage.tsx`, `PurchaseOrdersListPage.tsx` — dropped
  the manual vendor-list lookup in favor of `vendor_name` from the API; expanded receipts section
  into per-line detail tables.
- `src/pages/receiving/ReceivePage.tsx`, `QuickReceivePage.tsx` — result screens now show a
  per-line reconciliation table instead of aggregate counts.
- `src/pages/operations/InventoryOnHandPage.tsx`, `DiscrepanciesPage.tsx`,
  `UnresolvedItemsPage.tsx` — real names throughout; discrepancies/unresolved views gained vendor
  and supplier-order-link columns; unresolved-items resolve action switched to the correct
  endpoint (see bug fix above).
- `src/pages/products/ProductDetailPage.tsx` — two new sections (Supplier Order Lines, Receiving
  Activity); inventory units table gained vendor/location columns.

**Docs:**
- `docs/design/erik-acceptance-click-through.md` (new) — the 16-step script below, as its own
  file for reuse.
- `docs/design/mvp-refinement-pass-report.md` (this file).

---

## 3. Tests Run and Results

```
cd backend && rm -f beadstore_dev.db && ./.venv/bin/python -m pytest -q
```
**37 passed**, 0 failed (up from 35 before this pass — 2 new tests added, no existing test needed
to change to accommodate the new fields since they're all additive/optional).

```
cd frontend && npx tsc -b
```
Clean, no errors.

```
cd frontend && npm run build
```
Succeeds (`vite build` completes; one pre-existing bundle-size advisory notice, unrelated to this
change, not an error).

```
cd frontend && npm run lint
```
One warning, pre-existing and unrelated to this pass: `AuthContext.tsx` exports a non-component
helper alongside a component, which trips oxlint's react-refresh convention rule. Not a defect.

**No failing tests.**

**Untested areas (unchanged from the prior audit, still accurate):** no frontend automated test
suite (typecheck + build only); no test exercises real Supabase network calls (validated manually
instead, see below); Render deployment remains undone and untested.

---

## 4. Manual Verification Completed

Ran a full scripted browser session (headless Chromium, real backend, real HTTP requests — not
mocked) covering: create vendor → create product with SKU → create a two-line supplier order
(one product-linked, one free-text) → mark ordered → partial receive (shortage) → receive
remainder (confirmed order reaches **Received**, not stuck on Partially Received — this re-tests
the reconciliation fix from the previous session) → product detail page (confirmed both new
history sections render with real data and working links) → inventory list (confirmed real names/
SKUs/vendors replace "Linked product") → discrepancies view (confirmed vendor/date/order-link
columns) → unresolved-items view → resolve action (confirmed the fixed resolve flow: matched item
disappears from the list, and — verified via direct API call — both the receipt line and its
inventory unit show the resolved product's name afterward, not just one of the two).

One real bug was caught and fixed during this manual pass, separate from the resolve-endpoint bug
described in Section 1: `describeItem()` initially didn't recognize `unresolved_item_description`
(the field name specific to receipt lines — inventory units use `unresolved_description`, purchase
order lines use `expected_item_description`, and receipt lines use yet a third name). This caused
receipt lines in the PO detail page's Receipts section to show the generic fallback "Unresolved
item" instead of the actual typed-in description. Fixed by checking all three field names in the
helper; re-verified via screenshot afterward showing the correct text.

All screenshots from this session are available on request but are not included inline here.

---

## 5. Updated Known Issues

Carried forward from the prior self-audit, still accurate:
- No pagination controls in the UI (endpoints support it; not needed at current data volume).
- No frontend automated test suite.
- Render deployment undone and unverified.
- The Supabase legacy JWT secret shared during earlier troubleshooting should still be rotated
  (low urgency, unrelated to this pass).

Resolved by this pass (previously listed as "should fix before Patti business acceptance"):
- ~~List/discrepancy views show "Linked product" instead of the product name~~ — fixed.
- ~~Product detail page doesn't show PO/receipt history~~ — fixed.

New, smaller items noticed during this pass (not blocking, worth knowing about):
- A receipt line's discrepancy status is a permanent record of that specific receiving event. If
  an order is partially received with a shortage and later fully received, the original shortage
  entry remains visible in **Receiving Discrepancies** even though the order itself is now fully
  Received. This is intentional (an accurate history, not a live "problems right now" list) but
  worth explaining to Patti during the walkthrough so it doesn't read as a bug.
- The "unresolved" free-text field having three different names across three tables
  (`unresolved_description`, `expected_item_description`, `unresolved_item_description`) is a
  minor internal inconsistency that caused the bug described in Section 4. It's now handled
  correctly by the shared helper, but a future cleanup could unify the naming — deferred as
  cosmetic/internal, no functional impact remains.

---

## 6. New Risks Introduced

None identified. The relationship/property additions on the backend models are read-only
(`viewonly=True`) and additive to existing schemas (new fields are all `Optional`), so no existing
API consumer or test needed to change to tolerate them. The one behavioral change — the
unresolved-items page now calling a different endpoint to resolve items — was necessary to fix a
real bug (see Section 1) and is covered by both the existing backend test for that endpoint and
this session's manual verification.

---

## 7. Acceptance Recommendation

**Ready for Patti preview**, using the click-through script in
`docs/design/erik-acceptance-click-through.md`.

Reasoning: all six refinement goals were implemented and each was verified against a live backend
with real data, not just by inspection — including catching and fixing two real defects along the
way (the resolve-endpoint bug and the `describeItem` field-name gap) rather than just improving
appearance. The automated test suite grew from 35 to 37 tests and remains fully green, TypeScript
and the production build are both clean. The known issues in Section 5 are genuinely deferrable —
none of them block a business user from completing or understanding the workflows in the
click-through script. Recommend Erik runs that script once against his own Supabase-backed
instance as a final sanity check (should take under 15 minutes), then proceed directly to Patti's
walkthrough.
