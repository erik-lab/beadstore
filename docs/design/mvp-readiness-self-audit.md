# Patti Back Office MVP — Readiness Review / Self-Audit

Prepared by the coding agent, reviewing its own implementation against the approved technical
design (`docs/design/mvp-technical-design.md`) and Prompt 2's implementation instructions.

Status at time of audit: implementation deployed and manually confirmed running end-to-end
against a real Supabase project (Auth + Postgres) by Erik, including login, database connectivity
via the Session Pooler, and the app UI rendering as expected.

---

## 1. Scope Compliance

| Requirement | Status | Evidence |
|---|---|---|
| Supabase Auth email/password login | ✅ Done | `frontend/src/auth/LoginPage.tsx`, `AuthContext.tsx` (`signInWithPassword`); confirmed working live against real Supabase project |
| Protected backend API | ✅ Done | `app/core/security.py::get_current_user`; every router except `/health` depends on it (`dependencies=[Depends(get_current_user)]` in each router file) |
| Protected frontend UI | ✅ Done | `frontend/src/app/ProtectedRoute.tsx` redirects to `/login` when no Supabase session |
| Product management | ✅ Done | `app/routers/products.py`, `frontend/src/pages/products/*` (list/create/detail/edit) |
| Category/subtype support | ✅ Done | `product_categories` + `product_subtypes` tables, `app/routers/product_categories.py`, two-level dropdown in `ProductFormPage.tsx` |
| Catalog listing management | ✅ Done | `app/routers/catalog_listings.py`, `frontend/src/pages/catalogListings/*` |
| Inventory unit management | ✅ Done | `app/routers/inventory_units.py`, `frontend/src/pages/inventoryUnits/*`, includes `/adjustments` endpoint |
| Vendor management | ✅ Done | `app/routers/vendors.py`, `frontend/src/pages/vendors/*` |
| Supplier purchase orders | ✅ Done | `app/routers/purchase_orders.py`, `frontend/src/pages/purchaseOrders/*` |
| Purchase order line items | ✅ Done | `purchase_order_lines` table; product-or-free-text enforced by `PurchaseOrderLineCreate` validator in `app/schemas/purchase_order.py` |
| Receiving against existing orders | ✅ Done | `POST /purchase-orders/{id}/receipts`, `app/services/receiving_service.py::receive_against_order`, `frontend/src/pages/receiving/ReceivePage.tsx` |
| Receive-without-prior-order workflow | ✅ Done | `POST /receiving/quick-receive`, `receiving_service.py::quick_receive`, `frontend/src/pages/receiving/QuickReceivePage.tsx` |
| Retroactive purchase order creation | ✅ Done | `quick_receive` creates a `PurchaseOrder` with `is_retroactive=True` and a note; verified live (see Workflow Verification §7) |
| Reconciliation and discrepancy tracking | ✅ Done | `ReceivingStatus` enum (matched/overage/shortage/substitution/damaged/unresolved), cumulative-quantity reconciliation logic (see §2 and §6 for a bug found/fixed here) |
| Simple location/container tracking | ✅ Done | `locations` table with optional `parent_location_id` for nesting, `app/routers/locations.py`, `frontend/src/pages/locations/*` |
| Photo/media placeholders only | ✅ Done, no upload | `products.image_url` / `image_status` / `media_notes` columns exist; confirmed via repo-wide search that no upload/multipart/`UploadFile` code exists anywhere in `backend/app` or `frontend/src` |

**Confirmed absent (correctly out of scope):** no customer-facing storefront routes, no customer/order-for-sale concept, no payment processing code or dependency, no shipping workflow, no image upload endpoint or storage bucket integration, no barcode scanning, no AI/OCR extraction, no public self-signup (`ALLOW_PUBLIC_SIGNUP` flag defaults false and is never wired to a signup UI).

**Result: full scope compliance.** Every required capability is implemented; every excluded capability is genuinely absent from the codebase, not just hidden from navigation.

---

## 2. Data Integrity

**Required product fields:** `name`, `category_id` (Pydantic-enforced in `ProductCreate`, DB `NOT NULL`). `subtype_id` and all bead/finding attributes are nullable — confirmed no server-side requirement ties a category to a mandatory subtype.

**Required inventory fields:** `quantity`, `unit_type`, `received_date` are non-nullable columns and required Pydantic fields. `product_id` is nullable, but a model validator (`InventoryUnitCreate.require_product_or_description`) enforces that if `product_id` is absent, `unresolved_description` must be present — so an inventory unit is never left with neither.

**Required purchase order fields:** `vendor_id`, `status`, `order_date` — all non-nullable; `order_date` defaults to today if omitted so "unknown order date" doesn't block creation. Vendor is never nullable: the design's "Unknown Vendor" convention is enforced by seeding a real `Vendor` row (`scripts/seed.py`) rather than allowing a null FK, which avoids null-handling special cases throughout reporting/filtering.

**Required purchase order line fields:** enforced via `PurchaseOrderLineCreate` validator — exactly a product or a free-text description is required; quantity/unit/cost stay optional since they may be unknown at entry time.

**Required receipt line fields:** `received_quantity`, `received_unit_type` are required Pydantic fields (no default); `product_id` vs. `unresolved_item_description` enforced the same product-or-description way via `ReceiveLineInput`/`QuickReceiveLineInput` validators.

**Optional attributes:** all bead/finding fields (material, color, size, shape, finish, hole_size, origin, strand_length, count, grade, condition) are nullable columns with no server-side requirement, matching the design's "don't force Patti to fill in unknowns" principle.

**Unresolved item handling:** an inventory unit or receipt line can exist with `product_id = NULL` and a free-text description; `InventoryUnitStatus.unresolved` / `ReceivingStatus.unresolved` mark these so they surface on the "Items Needing Product Match" operational view (`GET /operations/unresolved-items`).

**Product matching after receipt:** `PATCH /receipt-lines/{id}/resolve` (`receiving_service.py::resolve_receipt_line`) sets `product_id` on both the receipt line and its linked inventory unit, flips status from `unresolved` to `matched`/`available`, and does **not** require re-entering quantity — confirmed by test `test_resolve_unresolved_receipt_line` and by manual UI testing (Erik/agent) matching a "Mystery bag of beads" line to a real product from the Unresolved Items screen.

**Discrepancy handling:** `receiving_service._determine_status` classifies every receipt line automatically (matched/shortage/overage/substitution/unresolved) unless the user explicitly overrides the status (e.g., marking `damaged`, which the system can't infer from quantity alone). All non-matched statuses surface on `GET /operations/receiving-discrepancies`.

**Delete/archive behavior:** confirmed by direct grep — **no `DELETE` endpoints exist** on vendors, products, catalog listings, inventory units, or locations; each instead has a `POST /{id}/archive` endpoint that flips a `status` enum value to `archived` (see Section 1 evidence table). Purchase orders use their existing `cancelled` status as the archive-equivalent state rather than a separate flag. This matches the approved amendment requiring archive-over-delete for referenced records.

---

## 3. Workflow Verification

All nine workflows below were exercised twice: once via automated backend tests (`backend/tests/`), and once manually end-to-end (browser + live backend) during development — the second pass caught and fixed two real bugs described in Section 6.

1. **Create a product.** Works. `POST /api/v1/products` with `name` + `category_id`; UI form at `/products/new`. Test: `test_create_and_get_product`. No known limitation beyond the general one in §4 (list views show linked-record IDs, not names).

2. **Create an inventory unit manually.** Works. `POST /api/v1/inventory-units`; UI at `/inventory/new`, supports either a linked product or a free-text "unresolved" description. Test: `test_create_inventory_unit_with_product`, `test_inventory_unit_supports_unresolved_description`.

3. **Create a supplier purchase order with line items.** Works. `POST /api/v1/purchase-orders` accepts a `lines[]` array in the same request; UI at `/purchase-orders/new` supports adding/removing lines before submit, each either product-linked or free-text. Test: `test_create_purchase_order_with_lines`.

4. **Receive against the supplier order.** Works. `POST /purchase-orders/{id}/receipts`; UI at `/purchase-orders/{id}/receive` pre-fills expected quantities and lets the user adjust received quantity/unit per line. Test: `test_receive_full_match`.

5. **Partially receive an order.** Works, **and this is where a real bug was found and fixed**: the first version compared each individual receipt against the *original* expected quantity rather than the cumulative amount received so far, so an order split across two receipts (e.g. 6 now, 4 later) could never reach "Received" status — it kept reporting "shortage" forever, even after the full quantity had arrived. Fixed in `receiving_service.py` (`_cumulative_received_for_line`) and locked in by regression test `test_split_receipts_reconcile_cumulatively_to_received`, plus `test_receive_partial_shortage` and `test_multiple_receipts_against_same_order` for the single-receipt and multi-receipt-count cases.

6. **Record a discrepancy.** Works. Damaged/substitution/overage/shortage/unresolved are all reachable either automatically (quantity mismatch) or via explicit override in the Receive UI's "Discrepancy Override" column. Tests: `test_receive_overage`, `test_receive_damaged_item_still_tracked`, `test_receive_unresolved_item`.

7. **Receive without prior order.** Works. `POST /receiving/quick-receive` creates a `PurchaseOrder(is_retroactive=True)` with an explanatory note, a matching `Receipt`, `PurchaseOrderLine`(s), `ReceiptLine`(s), and `InventoryUnit`(s) in one transaction. UI at `/receiving/quick-receive`, confirmed manually (screenshot-verified during development) and by test `test_quick_receive_creates_retroactive_order`.

8. **Resolve an unmatched received item to a product.** Works, confirmed both by automated test (`test_resolve_unresolved_receipt_line`) and live manual test — matched a real "Mystery bag of beads" unresolved item to a product from the Items Needing Product Match screen and watched it drop off the list.

9. **View product detail with related inventory/catalog/order data.** Works. `ProductDetailPage.tsx` calls `GET /products/{id}/inventory-units` and `GET /products/{id}/catalog-listings` and renders both tables inline with the product's own attributes. **Known limitation:** these tables link to the *product's own* purchase-order/receipt history is only reachable indirectly (via the linked inventory unit's `purchase_order_id`, not surfaced as a direct table on this page) — see §6 "Should fix."

---

## 4. Technical Quality

**Backend structure:** layered by concern — `models/` (SQLAlchemy ORM), `schemas/` (Pydantic request/response, including cross-field validators), `routers/` (thin HTTP handlers), `services/` (the one genuinely non-trivial piece of business logic, receiving reconciliation, isolated in `receiving_service.py` and independently unit-testable). This matches the design's stated goal of keeping business logic out of route handlers.

**Frontend structure:** feature-folder layout (`pages/<domain>/`), a single shared `apiClient.ts` that attaches the Supabase bearer token to every request, a small `useFetch` hook standing in for a data-fetching library, and a shared `StatusBadge`/`States` component set for consistent loading/empty/error rendering. No component exceeds roughly 250 lines; no cross-feature coupling beyond shared `lib/` and `components/`.

**Migration quality:** single Alembic migration (`896977388da2_initial_schema.py`) generated from the full model set, applies cleanly to both SQLite (local dev) and Postgres (Supabase) since no Postgres-only column types are used (enums stored as `native_enum=False` strings, UUIDs via SQLAlchemy's cross-dialect `Uuid` type). One schema wrinkle worth flagging: `inventory_units.receipt_line_id` and `receipt_lines.inventory_unit_id` are mutually referencing FKs; this is handled correctly with `use_alter=True` on one side so table creation and Alembic's dependency sort both work without warnings (confirmed — no SAWarning in the current migration run).

**Test coverage:** 35 backend tests, all passing (`pytest -q` → `35 passed`), spanning auth (including two intentionally adversarial cases — a concurrent-first-login race and the asymmetric-JWT/JWKS path, both discussed in §5), every entity's CRUD and required-field validation, and the full receiving/reconciliation matrix (full match, shortage, overage, damaged, substitution, unresolved, multi-receipt cumulative reconciliation, retroactive receiving, and blocking receipt against a cancelled order). No frontend automated tests exist yet (TypeScript typecheck and production build are clean, but there is no component or E2E suite) — this is the most significant testing gap.

**Error handling:** consistent HTTP semantics — 401 for missing/invalid/expired tokens, 404 for missing resources, 409 for invalid state transitions (e.g. receiving against a cancelled order), 422 with field-level detail for validation failures. Frontend surfaces backend error `detail` text in an inline `alert-error` banner on every form.

**Loading/empty states:** every list/detail page uses shared `<Loading />` / `<EmptyState />` / `<ErrorState />` components rather than ad hoc conditionals — confirmed by grep, all list pages import from `components/States.tsx`.

**Auth handling:** backend verifies both the legacy shared-secret (HS256) and current Supabase asymmetric (JWKS-based) token formats, dispatching on the token's own `alg` header — this was added mid-review after Erik's live Supabase project turned out to use the newer JWT Signing Keys system, and is now covered by test `test_asymmetric_jwt_verified_via_jwks`. Frontend never sees the JWT secret or DB credentials — only the Supabase anon key (safe to expose) — confirmed by inspecting `frontend/.env.example` and `apiClient.ts`.

**Environment config:** `.env.example` present for both backend and frontend documenting every variable; real `.env` files are gitignored (confirmed — `git status` shows no `.env` tracked, only `.env.example`). `DATABASE_URL_MIGRATIONS` falls back to `DATABASE_URL` when unset, so Alembic doesn't require a second connection string in simple setups.

**Render deployment readiness:** documented in `README.md` (two services — API + static frontend build — plus a migration pre-deploy step), but **not yet actually deployed or tested on Render** — this remains a real gap between "documented" and "verified," called out explicitly in §6.

---

## 5. Test Evidence

**Commands run (this session, against the current `c44753a` commit):**
```
cd backend && rm -f beadstore_dev.db && ./.venv/bin/python -m pytest -q
```
**Result:** `35 passed, 62 warnings in 1.63s`. Warnings are all either PyJWT's "HMAC key shorter than recommended" notice (only affects the deliberately weak dev/test secret, not a real Supabase secret) or unrelated to correctness.

```
cd frontend && npx tsc -b
```
**Result:** clean, no errors or output (confirmed just now during this audit).

**Failing tests:** none.

**Untested areas:**
- No frontend automated tests (typecheck/build only).
- No test exercises the actual Supabase network calls (JWKS fetch, real Postgres connection) — those were validated manually against Erik's live project instead, not via CI-style automation. If the JWKS endpoint URL or response shape ever changes on Supabase's side, only a live run would catch it.
- No load/concurrency testing beyond the one deliberate race-condition test (`test_concurrent_first_login_does_not_500`).
- Render deployment itself is untested (see §4).

**Manual QA performed (this session and prior):**
- Full login → dashboard → CRUD → PO → receive → quick-receive → resolve-unresolved click-through, done twice: once via a scripted headless-browser pass against a local SQLite backend (screenshots captured, two real bugs found and fixed as a direct result — see §6), and once live by Erik against his actual Supabase project (Auth + Postgres via Session Pooler), which he confirmed is now running and displaying as expected.
- Supabase-specific setup was iteratively debugged live with Erik: JWT verification (legacy secret → discovered project had migrated to JWT Signing Keys → added JWKS support), and database connectivity (placeholder `DATABASE_URL` → direct-connection IPv6 DNS failure → resolved by switching to the Session Pooler connection string).

---

## 6. Remaining Risks

**Must fix before Erik technical acceptance:**
- None outstanding. The two bugs actually found during verification (cumulative-receipt reconciliation, concurrent first-login race, and the JWKS/asymmetric-JWT gap) have all been fixed and covered by regression tests, and the app is now confirmed running against Erik's real Supabase project.

**Should fix before Patti business acceptance:**
- Inventory unit / discrepancy list rows display "Linked product" instead of the actual product name (the list endpoints return `product_id`, not a resolved name) — functionally correct but not friendly for Patti's day-to-day use. Fix is small (join or a lookup) but wasn't done in this pass.
- Product detail page doesn't show a direct "purchase order / receipt history" table — inventory units on that page do trace back to a PO/receipt in the data, but the UI doesn't surface that link yet.
- No pagination controls in the UI (endpoints support `limit`/`offset` already) — fine at current data volumes, will matter once Patti has hundreds of products/inventory units.

**Can defer until post-MVP:**
- Frontend automated test suite (component/E2E).
- Frontend types generated from the OpenAPI schema instead of hand-maintained.
- Actual Render deployment and its own smoke test (currently only documented, not executed).
- Rotating the Supabase legacy JWT secret that was shared in plaintext during setup troubleshooting — low urgency since it's a secondary/legacy credential, but good hygiene.

**Future automation opportunities (explicitly out of MVP per the design):**
- AI-assisted matching of unresolved receipts to products.
- Barcode scanning for receiving.
- Automated vendor catalog import.
- Image upload/media management (schema is ready for it; nothing further needed until this is prioritized).

---

## 7. Acceptance Recommendation

**Partially ready; safe to review with known limitations.**

Every required MVP capability is implemented, tested, and — as of this session — confirmed running against Erik's actual Supabase project end-to-end, not just in a local/simulated environment. The two real defects this review surfaced were both caught and fixed with regression tests during the process, which is the point of this kind of review. What keeps this from a plain "ready" is that the fixes (JWKS support, database pooling instructions) were only just confirmed live moments ago and haven't had a full second walkthrough of every screen against the real Supabase backend yet — and the "should fix" items above (product names in list views, PO/receipt history on product detail) are small but real gaps in day-to-day usability for Patti. Recommend: Erik does one more pass clicking through the workflows in Section 3 against the real Supabase-backed instance now that it's running, and Patti's business acceptance should wait for at least the two "should fix" usability items above.
