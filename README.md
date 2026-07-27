# Patti Back Office

Internal back-office web app for inventory, product, catalog, supplier order, and receiving
management. Not a customer-facing storefront. See `docs/design/mvp-technical-design.md` for the
approved technical design this implementation follows.

- **Backend**: FastAPI + SQLAlchemy + Alembic, in `backend/`
- **Frontend**: React + Vite + TypeScript, in `frontend/`
- **Database / Auth**: Supabase-hosted Postgres + Supabase Auth (email/password)

## Local Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env   # edit values, see Environment Variables below
./.venv/bin/alembic upgrade head
./.venv/bin/python scripts/seed.py
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. Health check: `GET /health`.

For quick local development without a Supabase Postgres instance, `DATABASE_URL` can be left as
the SQLite default in `.env.example` (`sqlite:///./beadstore_dev.db`) — SQLAlchemy models avoid
Postgres-only types so the same code runs against either. Use a real Supabase Postgres URL for
anything beyond local iteration.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # edit values, see Environment Variables below
npm run dev
```

Frontend runs at `http://localhost:5173` and expects the backend at
`VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`).

## Environment Variables

### Backend (`backend/.env`)

| Variable | Purpose |
|---|---|
| `ENV` | `local` / `staging` / `production` |
| `DATABASE_URL` | App DB connection (pooled connection when using Supabase) |
| `DATABASE_URL_MIGRATIONS` | Direct (non-pooled) DB connection for Alembic; falls back to `DATABASE_URL` if unset |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_JWT_SECRET` | Used to verify Supabase-issued JWTs (Project Settings → API → JWT Secret) |
| `SUPABASE_JWT_AUDIENCE` | Expected JWT audience, normally `authenticated` |
| `ALLOW_PUBLIC_SIGNUP` | Feature flag, keep `false` — accounts are created manually (see Supabase Setup) |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend API base URL, e.g. `http://localhost:8000/api/v1` |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public key (safe to expose to the browser) |

Neither `.env` file should ever contain a Supabase **service role** key — the frontend only uses
the anon key for the Auth SDK, and all data access goes through the FastAPI backend rather than
direct browser-to-database calls.

## Supabase Setup

1. Create a Supabase project (Erik).
2. In **Authentication → Providers**, keep Email enabled and disable public sign-ups if the
   project-level toggle allows it — self-signup is also blocked at the app layer
   (`ALLOW_PUBLIC_SIGNUP=false`).
3. Create one Supabase Auth user per person (Patti and Erik), each with their own email/password —
   no shared credentials. This can be done from the Supabase dashboard under
   **Authentication → Users → Add user**.
4. Copy the project URL and anon key into `frontend/.env`.
5. Copy the project URL and JWT secret (**Project Settings → API → JWT Secret**) into
   `backend/.env`.
6. Copy the Postgres connection string (**Project Settings → Database**) into
   `backend/.env` as `DATABASE_URL` (pooled/session mode) and `DATABASE_URL_MIGRATIONS`
   (direct connection, used only for running Alembic).

## Migrations

```bash
cd backend
./.venv/bin/alembic upgrade head          # apply migrations
./.venv/bin/alembic revision --autogenerate -m "describe change"   # generate a new migration after model changes
```

## Seed Data

```bash
cd backend
./.venv/bin/python scripts/seed.py
```

Seeds: product categories (Beads, Findings) with example subtypes, a system "Unknown Vendor"
record (used when a supplier order's vendor isn't known), one demo vendor, one demo location, and
one demo product with an inventory unit. Safe to re-run — it's idempotent.

## Tests

### Backend

```bash
cd backend
./.venv/bin/python -m pytest -q
```

34 tests covering: auth (including the profile-auto-provisioning race condition), product CRUD
and validation, inventory unit CRUD and adjustments, purchase order creation and line validation,
receiving against an existing order (full match, shortage, overage, damaged, substitution,
unresolved, multiple receipts against the same line reconciling cumulatively), retroactive
receiving with no prior order, and required-field validation across the API.

### Frontend

```bash
cd frontend
npx tsc -b        # typecheck
npm run build     # production build
```

There is no automated frontend test suite in this MVP (see Known Limitations). Manual
verification steps are listed below and were exercised against a live backend + browser during
development.

## Deployment (Render)

- Two Render services: a Python service for `backend/` (`uvicorn app.main:app`) and a static site
  built from `frontend/` (`npm run build`, publish `frontend/dist`).
- Set `DATABASE_URL_MIGRATIONS` and run `alembic upgrade head` as a Render pre-deploy/release
  command against the direct (non-pooled) Supabase connection.
- Configure all environment variables listed above in the Render dashboard — never commit real
  secrets to the repo.
- Set `CORS_ORIGINS` on the backend service to the deployed frontend's URL.

## Manual Acceptance Checklist

Run through this after `docker`-free local setup (or against a deployed environment) with a real
Supabase project:

- [ ] Log in with a Patti/Erik Supabase account; confirm an unauthenticated visit to any route
      redirects to `/login`.
- [ ] Log out; confirm protected pages are no longer reachable.
- [ ] Create a vendor.
- [ ] Create a product (Beads or Findings category), leaving optional attributes blank.
- [ ] View the product detail page; confirm inventory/catalog sections show correctly when empty.
- [ ] Create a catalog listing for that product.
- [ ] Create an inventory unit directly (manual stock entry) for the product.
- [ ] Create a location and assign it on an inventory unit.
- [ ] Create a supplier order for the vendor with one product-linked line and one free-text line.
- [ ] Mark the order "Ordered".
- [ ] Receive against the order with a short quantity on one line; confirm the order shows
      "Partially Received" and the discrepancy appears under Receiving Discrepancies.
- [ ] Receive the remainder; confirm the order reaches "Received".
- [ ] Use "Receive without prior order"; confirm a retroactive supplier order and receipt appear
      under Supplier Orders, marked as created during receiving.
- [ ] Confirm the free-text/unresolved item from the previous step shows under "Items Needing
      Product Match", then match it to a product and confirm it drops off the list.
- [ ] Check the Dashboard counts reflect the above changes.

## Known Limitations

- No automated frontend test suite (component/E2E) — see Deferred Follow-ups below.
- Inventory unit and receiving-discrepancy list rows show "Linked product" rather than the
  product's name (the API returns product IDs; resolving names client-side was deferred to keep
  the MVP list endpoints simple — see Recommended Next Fixes).
- Frontend TypeScript types are hand-written to mirror the backend Pydantic schemas rather than
  generated from the OpenAPI spec (noted as a recommendation in the design doc; not done in this
  pass).
- No pagination controls in the UI yet, though list endpoints support `limit`/`offset`.
- Photos/media are placeholder fields only (`image_url`, `image_status`, `media_notes`) — no
  upload UI or storage, per the approved design.
- `lot` remains a valid backend unit type for internal costing use but is intentionally excluded
  from the UI's unit-type dropdown.

## Deferred Features (per approved design)

Customer-facing storefront, customer orders, payment processing, shipping workflow, image
upload/media management, barcode scanning/generation, automated vendor import, AI extraction/OCR,
complex accounting/tax handling, multi-warehouse fulfillment, and role-based permissions beyond
authenticated access.
