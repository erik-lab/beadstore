# API Tiers: Prep Work Plan

> **Status: Phase 0 and Phase 1 are done** (see "What's actually built" below). Phases 2-3 are
> deliberately not started — see the original rationale at the bottom, which still holds.

Context: today there's one API (`/api/v1/*`), used only by the internal dashboard, authenticated
by Supabase JWT (Patti/Erik). Two more consumers are coming — a storefront app, and an Etsy
integration — each needing a narrower, differently-authenticated slice of this API. This is an
audit of what's in the way, and a phased plan to clear it, done *before* either of those APIs has
real requirements, so we're not guessing at shapes we'll throw away.

## Audit: routers today

| Router | Lines | Logic location | Relevant to storefront/Etsy? |
|---|---|---|---|
| `products.py` | 161 | Inline in router (simple CRUD) | Yes — read path |
| `catalog_listings.py` | 79 | Inline in router (simple CRUD) | Yes — this *is* the storefront-facing data |
| `inventory_units.py` | 123 | Inline in router, one real business rule (adjustment floor check) | Indirectly — stock source of truth |
| `purchase_orders.py` | 147 | Inline in router | No — inbound/vendor side only |
| `receiving.py` | 81 | Delegates to `services/receiving_service.py` | No |
| `piece_creations.py` | 50 | Delegates to `services/piece_service.py` | No |
| `vendors.py`, `locations.py`, `product_categories.py`, `hints.py` | — | Inline, trivial CRUD | No — internal reference data |
| `dashboard.py` | 126 | Inline, internal reporting | No |
| `email_accounts.py`, `order_email_parse.py`, `auth.py` | — | Staff-only workflows | No |
| `audit_log.py` | 35 | Delegates to model-level capture | No |

Most routers are simple CRUD with the logic inline — that's fine as-is; there's nothing to extract
when there's no real business rule (a two-line `db.get` + 404 check doesn't need a service layer).
`receiving.py` and `piece_creations.py` already show the pattern to follow when a router *does*
need one: router does auth + request/response shape, `services/*.py` does the actual work, so it's
callable from a second router with different auth wrapped around it.

**The routers that matter for this — `products.py` and `catalog_listings.py` — are exactly the
ones that are still all inline CRUD.** That's the concrete refactor target, but see the finding
below before starting: there's missing logic to write, not just logic to move.

## Key findings (the part that matters more than the refactor)

1. **`available_quantity_mode = derived_from_inventory` doesn't do anything.** It's a stored enum
   value, selectable in the catalog listing form, displayed in the UI — and there is no code
   anywhere that computes a derived quantity from inventory units. Today "availability" is either
   a manually-typed number or nothing. A storefront or Etsy listing absolutely needs real
   "how many can I actually sell right now" math (on-hand inventory minus what's reserved/already
   listed elsewhere), and that logic doesn't exist yet. This is new work, not a refactor.

2. **There's no outbound-sale concept at all.** The schema models the supply side in detail
   (vendors → purchase orders → receiving → inventory units) but nothing on the demand side.
   When a storefront or Etsy sale happens, something needs to decrement inventory and record the
   sale — there's no model, table, or service for that today. This is the single biggest piece of
   *new* work implied by "storefront" and "Etsy integration," and it's independent of the auth
   question — worth designing deliberately (probably its own `Sale`/`SaleLine` model + service,
   mirroring the existing receiving pattern in reverse) rather than bolted onto catalog_listings.

3. **Auth is hardcoded to one audience.** Every router does `dependencies=[Depends(get_current_user)]`,
   and `get_current_user` only knows how to verify a Supabase human JWT. A storefront and an Etsy
   integration are not "more restricted staff logins" — they're categorically different callers
   (no human, no Supabase session). Etsy in particular will hand us its own OAuth tokens to
   validate, not ours to issue. This needs a second, parallel auth dependency, not a permissions
   tweak to the existing one.

4. **No concept of "which caller made this request."** There's no API key / client identifier
   model anywhere. Once there are 3 faces, "measuring" them (your word) means being able to
   attribute a request to internal-dashboard vs. storefront vs. Etsy at minimum — today that
   information doesn't exist for anything but Supabase-authenticated staff.

## Phased plan

**Phase 0 — do now, cheap, no new surface exposed:**
- Extract `products.py` read endpoints and `catalog_listings.py` into a thin service layer
  (`services/catalog_service.py`), following the `receiving_service.py` pattern — router stays
  thin, logic becomes reusable. Low risk, ~1-2 files, no behavior change.
- Add a `ApiClient` (or `ApiConsumer`) model: `id`, `name`, `kind` (internal/storefront/etsy),
  `api_key_hash`, `status`, timestamps. Nothing uses it yet — this is just the identity table the
  next two phases need, and it's cheap to add now vs. retrofitting once real traffic exists.
- Add a second auth dependency, `get_api_client()`, alongside `get_current_user()` — verifies an
  API key against `ApiClient` instead of a Supabase JWT. Not wired into any router yet.

**Phase 1 — implement the actual missing logic (storefront-blocking regardless of auth):**
- Build the derived-availability calculation for `available_quantity_mode = derived_from_inventory`.
- Design and build the outbound-sale model + service (decrement inventory, record the sale,
  probably an audit-logged write path given the audit work already in place).

**Phase 2 — storefront-facing API surface:**
- New router(s) under a new prefix (e.g. `/api/storefront/v1`), read-mostly (published catalog
  listings, derived availability) plus the new sale-creation endpoint, authenticated via
  `get_api_client()` scoped to `kind = storefront`.

**Phase 3 — Etsy integration:**
- Etsy's real OAuth (they issue the tokens, not us) sits alongside `get_api_client()` as a third
  auth path, not a replacement for it.
- This is where a **local Etsy simulator** earns its keep, per your note — fake OAuth handshake +
  a handful of route stand-ins matching Etsy's real request/response shapes closely enough to
  exercise the integration code without live credentials or rate limits. Worth building once
  Phase 2's patterns (routes, auth plumbing) exist to mimic — building the simulator before that
  risks simulating the wrong shape twice.

## What's actually built (Phase 0 + 1, done)

**Phase 0:**
- `products.py` and `catalog_listings.py` are now thin routers over `services/product_service.py`
  and `services/catalog_service.py` — same behavior, logic is reusable from elsewhere now.
- `ApiClient` model/table (`name`, `kind`: internal/storefront/etsy, `api_key_hash`, `status`,
  `last_used_at`). Raw keys are generated with `core/api_keys.py` (`bsk_...` prefix, sha256 hash
  stored — high-entropy tokens don't need bcrypt's deliberate slowness) and shown exactly once, at
  creation.
- `get_api_client()` in `core/security.py` — reads `X-API-Key`, validates against `ApiClient`,
  updates `last_used_at`. `require_api_client_kind(kind)` factory to scope an endpoint to one face.
- Staff-only admin router `/api-clients` (create/list/revoke — gated on `get_current_user`, same as
  everything else staff uses).
- `/api-access/whoami` — the *first* real endpoint on the API-key auth path. Deliberately trivial
  (confirms identity, returns nothing else) — exists so a future storefront/Etsy integration has
  something to test its key against before any real business endpoint is built for it to call.

**Phase 1:**
- Derived availability is real now: `services/catalog_service.py::compute_derived_available_quantity`
  sums on-hand inventory for the listing's product, divided by `quantity_per_listing` (floored) —
  wired into every catalog-listing read path (list/get/create/update/archive), exposed as
  `derived_available_quantity` on `CatalogListingRead`, and shown on the listing detail page.
  Known limitation, unchanged from the original finding: doesn't yet account for stock already
  claimed by *other* listings selling the same product — that needs a reservation concept, which
  doesn't exist yet and wasn't in scope here.
- `Sale`/`SaleLine` models + `services/sales_service.py` — the demand-side counterpart to
  purchase-orders/receiving. Recording a sale resolves every line's product, validates aggregate
  demand *before* mutating anything (two lines for the same product are checked against combined
  demand, not each independently), then decrements inventory oldest-stock-first via the same
  `InventoryAdjustment` mechanism `piece_service.py` already uses for component consumption (new
  `sold` adjustment type) — so the audit trail stays consistent across both consumption paths.
  Staff-only router at `/sales` (create/list/get). Insufficient stock → 409, nothing partially
  decremented.
- **No frontend for recording a sale yet.** This shipped as API + service layer only, per the
  "prep work" framing — say the word if you want a UI for it next; today it's callable via the API
  directly (e.g. for manually logging an Etsy sale before the integration exists) but there's no
  page for it.

132 backend tests passing (39 new), frontend build/typecheck clean.

## What this plan deliberately does *not* do (Phases 2-3, still not started)

No storefront routes, no Etsy routes, no Etsy simulator yet — none of those have real requirements
today, and guessing at Etsy's exact request/response shapes before reading their API docs in
earnest would mean throwing work away. `get_api_client()` and `/api-clients` exist and work, but
nothing outside `/api-access/whoami` uses them yet — that's intentional, not an oversight.
