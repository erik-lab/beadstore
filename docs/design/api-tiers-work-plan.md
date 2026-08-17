# API Tiers: Prep Work Plan

> **Status: all four phases are done** (Erik: "I figured we were going to need this eventually
> anyway, so why not start now"). Sync direction for Etsy confirmed: **us → Etsy** — our catalog is
> the source of truth, pushed out; orders/inventory flow back. See "Phase 2/3 design" below for
> what that implies, and "What's actually built" for what exists and what's still genuinely
> untested (no real Etsy account exists yet — everything's been run against the built-in
> simulator).

## Phase 2/3 design

**Phase 2 (storefront-facing API):** new router at `/api/v1/storefront/*` (not a new URL prefix
outside `/api/v1` — same versioning, scoped by auth instead), gated on
`require_api_client_kind(ApiClientKind.storefront)`. Read-only catalog (published listings +
derived availability only — no cost, vendor, internal notes, or workflow-state fields; a dedicated
`StorefrontListingRead` schema, not the internal `CatalogListingRead`, enforces that at the type
level rather than by remembering to strip fields per-endpoint) plus `POST /storefront/orders`,
which is a thin wrapper over `sales_service.create_sale` with `channel=storefront`.

**Phase 3 (Etsy), given us → Etsy:** this needs real state, not just a read passthrough —
tracking which of our listings map to which Etsy listing, and reconciling stock touched from both
sides. Etsy's `createDraftListing` also requires several fields we have no home for today
(`taxonomy_id`, `shipping_profile_id`, `return_policy_id`, `who_made`, `when_made`) — these are
Etsy-specific quirks that don't belong on the core `CatalogListing` model (that's the whole point
of keeping this tier separated), so they live on a dedicated `EtsyListingSync` mapping row instead,
one per catalog listing that's been pushed.

Etsy specifics confirmed from their current docs (fetched during planning, not assumed from
training data):
- OAuth 2.0 with **mandatory PKCE** on every authorization request (S256 code_challenge).
- Granular scopes split by read/write (`listings_r`/`listings_w`, `transactions_r` for orders,
  etc.) — request only what push+pull actually needs.
- Real endpoints this integration calls: `createDraftListing`, `updateListingInventory`,
  `getShopReceipts` (`GET /shops/{shop_id}/receipts`).
- Etsy shipped a real `order.paid` **webhook** in late 2025 (signed payload, retry with backoff) —
  before that it was poll-only. Building for both: webhook as the primary path, polling as a
  fallback/backfill, since webhook delivery isn't guaranteed and a missed one shouldn't mean a
  permanently-missed order.
- Rate limits: 10,000 requests/day, 10/sec per app — the simulator enforces the same shape so
  integration code gets exercised against realistic throttling, not just happy path.
- Registering an app (keystring + shared secret) doesn't require an existing shop; testing the
  real OAuth + seller-scoped endpoints does. Not blocking this work — the simulator doesn't need
  either.

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

132 backend tests passing (39 new), frontend build/typecheck clean. A no-frills "Record a Sale"
page shipped separately under Utilities right after this, for Patti/Erik to test the sales backend
by hand — see git history, not repeated here.

**Phase 2 (storefront API):**
- `StorefrontListingRead`/`StorefrontListingPage`/`StorefrontOrderCreate` schemas — a genuinely
  separate type from `CatalogListingRead`, not a filtered view of it, so a staff-only field added
  to the internal schema later can't leak out here by omission.
- `services/storefront_service.py` + router at `/api/v1/storefront/*`
  (`GET /listings`, `GET /listings/{id}`, `POST /orders`), gated on
  `require_api_client_kind(ApiClientKind.storefront)`. Only `published` listings are ever visible;
  an unpublished listing's id returns 404, not a hint that it exists in another state.
- `POST /storefront/orders` resolves price and product **server-side from the listing**, never
  from the request body — a storefront (or anything with a storefront key) can say what and how
  many, never what it costs. Thin wrapper over `sales_service.create_sale` with `channel=storefront`.
- 9 tests: auth scoping (missing key, wrong kind), published-only visibility, internal-field
  exclusion, derived-availability passthrough, price-tampering resistance, and that a
  storefront-created sale shows up correctly in the staff `/sales` list.

**Phase 3 (Etsy):**
- `EtsyAccount` (encrypted refresh token, same crypto module as `EmailAccount`) and
  `EtsyListingSync` (push state + the Etsy-only fields `createDraftListing` requires —
  `taxonomy_id`, `shipping_profile_id`, `return_policy_id`, `who_made`, `when_made`, `is_supply` —
  that have no home on `CatalogListing` itself) models + migration.
- **A real, runnable Etsy simulator** (`app/etsy_simulator/`, mounted at `/etsy-simulator` only
  when `ETSY_SIMULATOR_ENABLED=true`): PKCE-validated OAuth (`/oauth/connect` auto-approves, since
  there's no human seller to click "allow" locally; `/v3/public/oauth/token` does real S256
  challenge/verifier checking — a mismatched verifier is rejected, tested explicitly), shop
  discovery (`/v3/application/users/{id}/shops`, matching how Etsy's real access tokens embed
  `user_id` rather than `shop_id`), `createDraftListing`, `updateListingInventory`,
  `getShopReceipts`, a QPS/QPD limiter shaped like Etsy's real one, and `/_simulator/*` test-only
  helpers (seed a fake paid order, fire a signed `order.paid` webhook at our own receiver) —
  clearly namespaced so they're never mistaken for real Etsy behavior.
- `services/etsy_service.py` — the real API client (PKCE generation, token exchange/refresh,
  the three application-API calls above), talking to `settings.etsy_api_base_url` — the simulator
  locally, `https://openapi.etsy.com/v3` in production. The calling code doesn't know which.
- `services/etsy_sync_service.py` — `push_listing` (create-draft-then-update-inventory, refuses to
  push if the Etsy-only required fields aren't set yet, records `sync_status`/`last_error` either
  way) and `pull_receipts` (dedupes against `Sale.external_order_id`, skips a receipt line it can't
  map to a pushed listing rather than failing the whole pull, decrements inventory and creates a
  `Sale` via the same `sales_service.create_sale` the storefront and manual-recording paths use).
- Router at `/etsy/*`: staff-only account connect/list/disconnect (same popup-postMessage OAuth
  pattern as `email_accounts.py`) and push/pull/sync-status endpoints, plus a public
  `POST /etsy/webhook` authenticated by HMAC signature (not staff auth) that triggers the same
  reconciling pull a manual "sync now" click would — idempotent and self-healing if a webhook
  delivery is ever missed, at the cost of one extra Etsy API call per delivery.
- No-frills "Etsy Integration" page under Utilities (connect a shop, push a listing, pull orders),
  same spirit as Record a Sale — a way to see it work, not a finished feature.
- 8 tests drive the **actual OAuth/PKCE handshake through the real router and the real simulator**
  (not mocked) — connect, push creates-then-updates correctly, pull creates a `Sale` and decrements
  inventory, a second pull doesn't double-count, and the webhook rejects a bad signature before
  accepting a valid one. Getting httpx to route through the in-process app for this needed
  `TestClient` specifically, not a raw `httpx.Client` + `ASGITransport` — the latter is async-only
  and `etsy_service.py`'s calls are sync, matching `gmail_service.py`/`outlook_service.py`'s style.

**What's still genuinely untested, because there's nothing to test it against:** the real Etsy
OAuth consent screen, real rate limiting/error shapes, and whatever's actually different between
the simulator's guesses (built from Etsy's *published* docs, fetched during planning — not
assumed from training data, but still never exercised against the live API) and the real thing.
That gap only closes once there's a real Etsy Developer Portal app and a shop to connect —
`ETSY_CLIENT_ID`/`ETSY_CLIENT_SECRET`/`ETSY_API_BASE_URL` in `.env.example` are exactly the three
settings that change when that happens; nothing else in the integration code should need to.
