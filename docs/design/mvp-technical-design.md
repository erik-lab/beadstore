# Patti Back Office MVP — Technical Design Proposal

Status: **Approved for implementation** (amendments incorporated below)
Scope: Internal back-office system for inventory, product, catalog, supplier order, and receiving management. No customer-facing storefront.

---

## 1. Architecture

### Frontend
- **React + Vite + TypeScript**, structured by feature rather than by type:
  ```
  frontend/
    src/
      app/                # router, layout shell, providers
      features/
        auth/
        products/
        catalogListings/
        inventoryUnits/
        vendors/
        purchaseOrders/
        receiving/
        locations/
        dashboard/
      lib/
        apiClient.ts       # fetch wrapper, attaches Supabase JWT
        supabaseClient.ts  # Supabase Auth SDK init
      components/          # shared UI primitives (table, form fields, status badges)
      types/                # shared TS types, ideally generated from OpenAPI
  ```
- Each feature folder owns its list/detail/create/edit views, hooks, and API calls.
- React Query (or equivalent) for server-state caching; plain React state/forms otherwise. Avoid heavier state libraries — not needed for MVP CRUD.
- Types generated from the FastAPI OpenAPI schema (e.g. `openapi-typescript`) to keep frontend/backend in sync without hand-maintained duplicate types.

### Backend
- **FastAPI**, structured by domain module:
  ```
  backend/
    app/
      main.py
      core/
        config.py          # env/settings
        security.py        # JWT validation, dependency for current_user
        db.py               # SQLAlchemy session/engine
      models/               # SQLAlchemy ORM models
      schemas/              # Pydantic request/response schemas
      routers/
        auth.py
        products.py
        catalog_listings.py
        inventory_units.py
        vendors.py
        purchase_orders.py
        receiving.py
        locations.py
        dashboard.py
      services/             # business logic (reconciliation, retroactive PO creation)
      alembic/               # migrations
    tests/
  ```
- Business logic (e.g., receiving reconciliation, retroactive order creation) lives in `services/`, not in routers, so it's independently testable.

### Database
- **Supabase-hosted Postgres.** Backend connects with SQLAlchemy using the Supabase Postgres connection string (session pooler for the app, direct connection for migrations).
- Supabase Auth's own `auth.users` table is managed by Supabase; our schema lives in `public` and references `auth.users.id` via a `profiles` table (see Data Model).

### Authentication integration
- Supabase Auth issues JWTs on login. Frontend uses `@supabase/supabase-js` for the auth flow only (not for direct data access). Backend validates JWTs on every request (see Section 2).

### Environment variables
| Variable | Used by | Purpose |
|---|---|---|
| `SUPABASE_URL` | frontend, backend | Supabase project URL |
| `SUPABASE_ANON_KEY` | frontend | Public key for Supabase Auth client |
| `SUPABASE_JWT_SECRET` | backend | Verify JWT signature (or JWKS URL if using asymmetric keys) |
| `DATABASE_URL` | backend | Postgres connection string (pooled) |
| `DATABASE_URL_MIGRATIONS` | backend/CI | Direct (non-pooled) connection for Alembic |
| `ALLOW_PUBLIC_SIGNUP` | backend | Feature flag, default `false` |
| `CORS_ORIGINS` | backend | Allowed frontend origin(s) |
| `ENV` | backend | `local` / `staging` / `production` |

### Local development
- `docker-compose` optional; simplest path is:
  - Backend: `uvicorn app.main:app --reload`, pointed at a Supabase dev project (or local Postgres for offline dev, with Alembic targeting either).
  - Frontend: `vite dev` with `VITE_API_BASE_URL` pointing at local backend.
  - `.env.example` files in both `frontend/` and `backend/` documenting required vars.
- Seed script (`backend/scripts/seed.py`) to populate baseline categories (Beads, Findings), a demo vendor, and a couple of products for local testing.

### Deployment (Render)
- Two Render services: `beadstore-api` (FastAPI, Docker or native Python) and `beadstore-web` (static site build from Vite `dist/`).
- Alembic migrations run as a Render pre-deploy/release command against `DATABASE_URL_MIGRATIONS`.
- Environment variables configured in Render dashboard; secrets never committed.

---

## 2. Authentication and Security

- **Flow:** Frontend uses Supabase Auth's email/password sign-in (`supabase.auth.signInWithPassword`). Supabase issues a JWT (access token) + refresh token, persisted by the Supabase JS client (localStorage by default).
- **Authenticated requests:** `apiClient.ts` attaches `Authorization: Bearer <access_token>` from the current Supabase session to every FastAPI request. Supabase JS handles silent token refresh.
- **Backend validation:** A FastAPI dependency (`get_current_user`) verifies the JWT signature against `SUPABASE_JWT_SECRET` (HS256) or Supabase's JWKS endpoint (if using RS256/ES256, recommended for newer Supabase projects), checks expiry/audience, and extracts the Supabase user id (`sub`). Every non-auth route depends on this — no anonymous data access.
- **Unauthenticated blocking:** Backend returns 401 on missing/invalid token; frontend router redirects to `/login` if no active Supabase session, and a route guard wraps all authenticated pages.
- **Signup mode:** Public self-signup **disabled by default** (`ALLOW_PUBLIC_SIGNUP=false`). Patti and Erik each get their own individually created Supabase Auth account (dashboard or a one-off admin script) — no shared credentials. No role distinction between the two accounts is required for MVP; this is a single-role access model with separate logins, not a shared login. If a signup UI is desired later, it's gated behind the flag and/or invite tokens.
- **Secrets:** Service-role keys (if ever needed for admin scripts) stay server-side only, never shipped to frontend. Frontend only ever sees `SUPABASE_ANON_KEY`, which is safe to expose (RLS/backend enforcement is what actually protects data — see below).
- **Data access path:** All data reads/writes go through FastAPI, not direct Supabase client queries from the browser, per shared context. This means Postgres Row Level Security is a defense-in-depth nice-to-have, not the primary access control — the primary control is the JWT-checking FastAPI dependency layer.

---

## 3. Data Model

All tables include `id UUID PK default gen_random_uuid()`, `created_at`, `updated_at` unless noted. Required fields marked **(required)**.

### `profiles`
Mirrors `auth.users` for app-specific fields.
- `id UUID PK` — **(required)**, FK to `auth.users.id`
- `email` — **(required)**, denormalized for display
- `display_name` — nullable

### `vendors`
- `name` — **(required)**
- `contact_name`, `email`, `phone`, `notes` — nullable
- `status` — enum (`active`, `archived`), default `active` — archived rather than deleted once referenced by purchase orders/inventory units

### `product_categories`
- `name` — **(required)**, e.g. "Beads", "Findings"

### `product_subtypes`
- `category_id` FK → `product_categories` — **(required)**
- `name` — **(required)**

### `products`
- `name` — **(required)** (working title acceptable)
- `category_id` FK → `product_categories` — **(required)**
- `subtype_id` FK → `product_subtypes` — nullable
- `description` — nullable
- `sku` — nullable, unique if present
- Optional bead/finding attributes (nullable): `material`, `color`, `size`, `shape`, `finish`, `hole_size`, `origin`, `strand_length`, `count`, `grade`, `condition`
- `attributes_json` — nullable JSON/JSONB column for future optional attributes not yet promoted to a fixed column
- `image_url`, `image_status` (enum: `none`, `pending`, `available`), `media_notes` — nullable placeholders, no upload logic
- `status` — enum (`active`, `archived`), default `active` — archiving instead of deleting once a product is referenced by inventory/catalog/PO records

Attribute note: storing bead/finding attributes as typed nullable columns on `products` (rather than a fully generic EAV table) is simpler to build/query for MVP, with `attributes_json` as an escape hatch for future ad-hoc fields without a migration. See Section 10 for the tradeoff and recommendation.

### `catalog_listings`
- `product_id` FK → `products` — **(required)**
- `title` — **(required)**
- `listing_description` — nullable
- `price` — nullable (decimal)
- `status` — enum (`draft`, `ready`, `retired`, `archived`), default `draft`

### `locations`
- `name` — **(required)**, e.g. "Bin A3", "Front Cabinet Drawer 2"
- `description` — nullable
- `parent_location_id` FK → `locations` — nullable (allows simple nesting, e.g. shelf → drawer)
- `status` — enum (`active`, `archived`), default `active` — archived rather than deleted once referenced by inventory units

### `inventory_units`
- `product_id` FK → `products` — nullable (unresolved during receiving; see workflow)
- `unresolved_description` — nullable, used when `product_id` is null
- `quantity` — **(required)**, numeric
- `unit_type` — **(required)**, enum (`strand`, `container`, `bag`, `tube`, `count`, `gram`, `ounce`, `piece`, `pair`, `set`, `unknown`, `other`, `lot`) — `lot` retained internally for costing use but not surfaced as a normal UI choice (see UI Terminology, Section 6a)
- `status` — **(required)**, enum (`available`, `reserved`, `depleted`, `damaged`, `unresolved`, `archived`)
- `received_date` — **(required)**, date
- `cost_amount`, `cost_currency` — nullable
- `vendor_id` FK → `vendors` — nullable
- `purchase_order_id` FK → `purchase_orders` — nullable
- `receipt_line_id` FK → `receipt_lines` — nullable
- `location_id` FK → `locations` — nullable
- `notes` — nullable

### `purchase_orders`
- `vendor_id` FK → `vendors` — nullable (**required as a value**: either a real vendor or a placeholder "Unknown Vendor" row — see Section 10)
- `status` — **(required)**, enum (`draft`, `submitted`, `partially_received`, `received`, `closed`, `cancelled`) — internal value stays `submitted`; UI label reads **"Ordered"** (see Section 6a for terminology mapping)
- `order_date` — **(required)** (defaults to created date if unknown)
- `expected_date` — nullable
- `is_retroactive` — boolean, default `false` — set true when auto-created during no-PO receiving
- `notes` — nullable

`cancelled` doubles as the archive state for purchase orders — no hard delete once a PO has lines/receipts.

### `purchase_order_lines`
- `purchase_order_id` FK → `purchase_orders` — **(required)**
- `product_id` FK → `products` — nullable
- `expected_item_description` — nullable, **(required if `product_id` is null)** — free text
- `expected_quantity` — nullable
- `expected_unit_type` — nullable, same enum as `inventory_units.unit_type`
- `unit_cost` — nullable
- `status` — enum (`pending`, `partially_received`, `received`, `cancelled`), default `pending`

### `receipts`
- `purchase_order_id` FK → `purchase_orders` — **(required)** (always present, including retroactive ones)
- `received_date` — **(required)**
- `received_by` FK → `profiles` — nullable
- `notes` — nullable
- `voided_at` — nullable timestamp — set instead of deleting a receipt entered in error, preserving the record and any inventory it already generated

### `receipt_lines`
- `receipt_id` FK → `receipts` — **(required)**
- `purchase_order_line_id` FK → `purchase_order_lines` — nullable (null when there was no matching expected line)
- `product_id` FK → `products` — nullable
- `unresolved_item_description` — nullable, **(required if `product_id` is null)**
- `received_quantity` — **(required)**
- `received_unit_type` — **(required)**
- `receiving_status` — **(required)**, enum (`matched`, `overage`, `shortage`, `substitution`, `damaged`, `unresolved`)
- `discrepancy_notes` — nullable
- `inventory_unit_id` FK → `inventory_units` — nullable, set once the receipt line generates/updates an inventory unit
- `voided_at` — nullable timestamp — same correction-without-deletion pattern as `receipts.voided_at`

### `inventory_adjustments`
- `inventory_unit_id` FK → `inventory_units` — **(required)**
- `adjustment_type` — enum (`manual_correction`, `damaged`, `lost`, `count_correction`, `other`)
- `quantity_delta` — **(required)**
- `reason` — nullable
- `adjusted_by` FK → `profiles` — nullable
- `adjusted_at` — **(required)**, timestamp

---

## 4. Product, Catalog, and Inventory Relationship

- **Product** is the conceptual/identifiable item (e.g. "6mm round faceted amethyst"). One row regardless of how many strands or containers exist.
- **Inventory Unit** is physical stock: a product can have many inventory units (multiple strands received at different times, different costs, different locations). Inventory units are the source of truth for "what do we physically have."
- **Catalog Listing** is a future-facing description of how a product might be presented for sale (title, listing copy, price). A product can have zero, one, or multiple catalog listings (e.g. different pricing/bundling ideas). Catalog data is purely descriptive and never affects inventory counts.
- **Traceability:** Inventory units optionally link back to the `purchase_order` and `receipt_line` they originated from, so "where did this stock come from" is always answerable without inventory units being *required* to have that link (manual stock entry with no PO is allowed).
- **Resolution flow:** Purchase order lines and receipt lines can start with only a free-text description (`expected_item_description` / `unresolved_item_description`) and no `product_id`. A later "resolve to product" action sets `product_id` on the line (and on any inventory units created from it) without altering historical quantities.
- This separation keeps "what could we sell and how" (catalog) distinct from "what do we have and where" (inventory), which is the core operational distinction Patti thinks in.

---

## 5. Supplier Order and Receiving Workflow

1. **Create vendor** — simple form, `name` required.
2. **Create purchase order** — pick vendor (or leave as "Unknown," see Section 10), set order date, status starts `draft` → `submitted` (shown to Patti/Erik as **"Ordered"**).
3. **Add expected order lines** — each line either linked to an existing product (typeahead search) or a free-text description; optional expected quantity/unit type/unit cost.
4. **Receive against an existing order:**
   - Open PO → "Receive" action → creates a `receipt` tied to that PO.
   - For each expected line, enter received quantity/unit type.
   - System reconciles automatically, covering every discrepancy case required for MVP:
     - received == expected (no quantity difference) → `matched`
     - received < expected → `shortage`, including **partial receipt** (line stays `partially_received` on the PO line until resolved or accepted)
     - received > expected → `overage`
     - different item received than expected → user marks `substitution` and can link a different product
     - visibly damaged → user marks `damaged`, still creates inventory unit (status `damaged`) so it's tracked, not silently dropped
     - received item doesn't match any known product → `unresolved` (an **unresolved received item**, surfaced as **product match needed**)
   - Each receipt line that isn't purely a shortage-with-nothing-received generates one `inventory_unit` (product optionally unresolved) linked back to the receipt line.
   - PO line `status` updates based on cumulative received quantity; PO `status` becomes `partially_received` or `received` once all lines are settled.
5. **Shortcut receiving (no prior order):**
   - "Quick Receive" screen: pick/create vendor (or "Unknown"), enter items received directly (product or free text, quantity, unit type, cost).
   - On save, backend **auto-creates** a `purchase_order` with `is_retroactive = true`, `status = 'received'`, one `purchase_order_line` per item entered (mirroring what was received), a `receipt`, and matching `receipt_lines` with `receiving_status = 'matched'`. This keeps a single consistent history model — every receipt always has a PO, some are just retroactive — instead of a parallel "no-PO" data path.
   - Resulting inventory units are otherwise identical to normal-flow ones.
6. **Unresolved items** — receipt lines/inventory units with no `product_id` show up in an "Items needing product match" operational view; resolving them later updates the linked records without re-entering quantities.

---

## 6. UI Screens and Routes

| Route | Purpose |
|---|---|
| `/login` | Email/password sign-in |
| `/` (Dashboard) | Summary: open orders, unresolved items, low/zero-stock flags (if trivial), recent receiving activity |
| `/products` , `/products/new`, `/products/:id`, `/products/:id/edit` | Product CRUD |
| `/catalog-listings`, `/catalog-listings/new`, `/catalog-listings/:id`, `/catalog-listings/:id/edit` | Catalog listing CRUD |
| `/inventory`, `/inventory/new`, `/inventory/:id`, `/inventory/:id/edit` | Inventory unit CRUD, filterable by product/location/status |
| `/vendors`, `/vendors/new`, `/vendors/:id`, `/vendors/:id/edit` | Vendor CRUD |
| `/purchase-orders`, `/purchase-orders/new`, `/purchase-orders/:id`, `/purchase-orders/:id/edit` | PO + line item management |
| `/purchase-orders/:id/receive` | Receiving workflow against a specific PO |
| `/receiving/quick-receive` | Shortcut receiving with no prior order |
| `/locations`, `/locations/new`, `/locations/:id/edit` | Location/container CRUD |
| `/operations/open-orders` | Orders not yet fully received |
| `/operations/unresolved-items` | Receipt lines/inventory units without a linked product |
| `/operations/inventory-on-hand` | Current stock view, filterable by category/subtype/location |
| `/operations/receiving-discrepancies` | Shortage/overage/substitution/damaged log |

---

## 6a. UI Terminology

Internal/database naming can stay technical; the UI uses Patti-friendly language throughout:

| Internal concept | UI wording |
|---|---|
| `inventory_units` | Inventory unit / stock record |
| `unit_type = strand` | Strand |
| `unit_type = container` | Container |
| `unit_type = lot` | Not shown as a selectable option; used only where internally needed for costing |
| `receipt_lines` | Received item |
| `products` | Product |
| `catalog_listings` | Catalog listing |
| `vendors` | Vendor |
| `purchase_orders` | Supplier order |
| `purchase_orders.status = submitted` | "Ordered" |
| `receipts` | Receipt |
| `receiving_status` values (`shortage`/`overage`/`substitution`/`damaged`/`unresolved`) | Discrepancy (with the specific type shown, e.g. "Shortage") |

`lot` is never presented as a normal dropdown choice; if it's ever needed operationally (e.g. costing rollups) it stays a backend/reporting concept.

---

## 7. API Endpoints

Base path `/api/v1`. All routes below require auth unless noted.

**Auth**
- `GET /auth/me` — current profile from validated JWT

**Vendors**
- `GET /vendors`, `POST /vendors`, `GET /vendors/{id}`, `PATCH /vendors/{id}`, `POST /vendors/{id}/archive` (sets `status = archived`; no hard delete once referenced)

**Product categories / subtypes**
- `GET /product-categories`, `POST /product-categories`
- `GET /product-categories/{id}/subtypes`, `POST /product-subtypes`

**Products**
- `GET /products` (filter by category/subtype/status, search by name), `POST /products`, `GET /products/{id}`, `PATCH /products/{id}`, `POST /products/{id}/archive`

**Catalog listings**
- `GET /catalog-listings`, `POST /catalog-listings`, `GET /catalog-listings/{id}`, `PATCH /catalog-listings/{id}`, `POST /catalog-listings/{id}/archive`

**Inventory units**
- `GET /inventory-units` (filter by product/location/status), `POST /inventory-units`, `GET /inventory-units/{id}`, `PATCH /inventory-units/{id}`
- `POST /inventory-units/{id}/adjustments` — create adjustment + apply quantity delta

**Locations**
- `GET /locations`, `POST /locations`, `GET /locations/{id}`, `PATCH /locations/{id}`, `POST /locations/{id}/archive`

**Purchase orders**
- `GET /purchase-orders` (filter by status/vendor), `POST /purchase-orders`, `GET /purchase-orders/{id}`, `PATCH /purchase-orders/{id}`
- `POST /purchase-orders/{id}/lines`, `PATCH /purchase-order-lines/{id}`, `DELETE /purchase-order-lines/{id}`

**Receiving**
- `POST /purchase-orders/{id}/receipts` — create a receipt against an existing PO, body = list of `{purchase_order_line_id | null, product_id | null, unresolved_item_description, received_quantity, received_unit_type, receiving_status}`
- `POST /receiving/quick-receive` — shortcut flow; body = list of items; server creates retroactive PO + receipt + lines + inventory units
- `GET /receipts/{id}` , `GET /purchase-orders/{id}/receipts`
- `PATCH /receipt-lines/{id}/resolve` — attach a `product_id` to a previously unresolved line, propagates to linked inventory unit

**Operational views**
- `GET /operations/open-orders`
- `GET /operations/unresolved-items`
- `GET /operations/inventory-on-hand`
- `GET /operations/receiving-discrepancies`

**Validation/error behavior:** 422 with field-level errors for schema violations (Pydantic), 404 for missing resources, 409 for conflicting state transitions (e.g. receiving against a `cancelled` PO), 401/403 for auth failures. Error responses use a consistent envelope: `{"detail": str | list[FieldError]}`.

---

## 8. Validation Rules

**Product:** `name`, `category_id` required. `subtype_id` optional (UI may prompt if category conventionally has subtypes, but not enforced server-side for MVP).

**Inventory Unit:** `quantity`, `unit_type`, `status`, `received_date` required. `product_id` required **unless** `status = 'unresolved'`, in which case `unresolved_description` is required instead.

**Supplier Order:** `status`, `order_date` required. `vendor_id` required as a value — use a system "Unknown Vendor" record rather than allowing null, to keep FK integrity simple (see Section 10).

**Supplier Order Line:** `purchase_order_id` required; either `product_id` or `expected_item_description` required (exactly one path, enforced at the API layer). `expected_quantity`/`expected_unit_type` optional.

**Receipt Line:** `received_quantity`, `received_unit_type`, `receiving_status` required. Either `product_id` or `unresolved_item_description` required.

---

## 9. Implementation Phases

1. **Project foundation and auth** — repo scaffold, Supabase project wiring, login flow end-to-end, protected route/API skeleton, deployment pipeline stub.
2. **Database schema and migrations** — all core tables via Alembic, seed script for categories.
3. **Backend CRUD APIs** — vendors, products, catalog listings, inventory units, locations.
4. **Frontend layout and core CRUD** — shared layout/nav, list/detail/create/edit for the above entities.
5. **Supplier order entry** — PO + line CRUD, product-or-free-text line handling.
6. **Receiving/reconciliation workflow** — receive-against-PO, quick-receive shortcut, retroactive PO creation, discrepancy statuses.
7. **Operational dashboard/views** — open orders, unresolved items, inventory on hand, discrepancies.
8. **Testing, seed data, documentation, readiness review** — backend test coverage on services (reconciliation, retroactive creation), frontend smoke tests on core flows, README + setup docs, walkthrough for Patti/Erik acceptance.

Each phase should be reviewable/mergeable independently.

---

## 10. Risks, Questions, and Recommendations

**Blocking questions** (need Erik/Patti input before or during Phase 1–2):
- Confirm Supabase project ownership/credentials will be provisioned by Erik before Phase 1 starts, including separate Patti and Erik user accounts created in Supabase Auth.
- Confirm Render account/services will be provisioned by Erik, or whether deployment is deferred past MVP code-complete.

**Non-blocking assumptions** (proceeding unless corrected):
- Patti and Erik each get an individually created Supabase Auth account (single-role access model, no shared credentials, no role distinction in UI/API for MVP).
- "Unknown Vendor" is represented as a real seeded `vendors` row rather than a nullable FK, to avoid nullable-FK edge cases throughout receiving/reporting.
- Bead/finding attributes are modeled as fixed nullable columns on `products`, plus a nullable `attributes_json` column for future ad-hoc attributes. This is simpler and query-friendly for two categories; if more categories with very different attribute sets are added later, revisit with a generic attributes table.
- Currency is single-currency (USD) for MVP; no multi-currency handling.
- Archiving (status flags / `voided_at`) replaces hard deletes for vendors, locations, products, catalog listings, purchase orders, receipts, receipt lines, and inventory units.

**Recommendations** (adjustable):
- Generate frontend TypeScript types from the FastAPI OpenAPI schema rather than hand-maintaining a parallel type system.
- Keep reconciliation/retroactive-order logic in a `services/` layer with direct unit tests, since it's the highest-risk business logic in the MVP.
- Keep the UI terminology mapping in Section 6a as the single source of truth for labels, so internal enum values (e.g. `submitted`, `lot`) never leak into Patti-facing screens.

**Deferred opportunities** (explicitly out of MVP, noted for later):
- Image upload and media management (placeholders only for now).
- Barcode scanning/generation.
- Multi-warehouse/location hierarchies beyond simple parent/child nesting.
- Role-based permissions beyond authenticated/unauthenticated.
- AI-assisted product matching for unresolved receiving items.
- Public customer-facing storefront and order processing.

---

## Ready for implementation after approval

- [x] Erik/Patti review and approve this design document (approved, with amendments incorporated above)
- [ ] Supabase project provisioned; separate Patti and Erik accounts created
- [ ] Render services (or deployment target) confirmed
- [ ] Blocking questions above resolved or explicitly deferred
- [x] Non-blocking assumptions confirmed or corrected (updated per approval amendments)
- [ ] Green light to begin Phase 1 (project foundation and auth)
