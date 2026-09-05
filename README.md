# Patti Back Office

Internal back-office web app for inventory, product, catalog, supplier order, and receiving
management. Not a customer-facing storefront. See `docs/design/mvp-technical-design.md` for the
approved technical design this implementation follows.

- **Backend**: FastAPI + SQLAlchemy + Alembic, in `backend/`
- **Frontend**: React + Vite + TypeScript, in `frontend/`
- **Database / Auth**: Supabase-hosted Postgres + Supabase Auth (email/password)

## Local Setup

> **Windows (Git Bash) users:** a venv's executables live in `.venv/Scripts/` on Windows, not
> `.venv/bin/` (that's the Linux/Mac layout) — swap `bin` for `Scripts` in every `./.venv/bin/...`
> command anywhere in this README, not just this section. If a command run through an *activated*
> venv (prompt shows `(.venv)`) still says "command not found," the package was never actually
> installed into it — run the `pip install` step again rather than assuming activation alone did
> something. See **Troubleshooting** below for the most common Windows pip failure (a certificate
> error).

This project runs on non-default ports — **8123** for the backend, **5193** for the frontend —
rather than FastAPI's/Vite's own defaults (8000/5173), to avoid clashing with other projects on the
same machine (see `docs/design/dev-cheat-sheet.md`). Both commands below already pass the right
`--port`; if you ever start either without it, you'll get the wrong default and every request from
the other side will fail with "Failed to fetch" (frontend pointed at a port nothing's listening on)
or a CORS error (backend not expecting that origin) — see **Troubleshooting**.

### 1. Backend

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env   # edit values, see Environment Variables below
./.venv/bin/alembic upgrade head
./.venv/bin/python scripts/seed.py
./.venv/bin/python scripts/seed_attribute_picklists.py
./.venv/bin/uvicorn app.main:app --reload --port 8123
```

Backend runs at `http://localhost:8123`. Health check: `GET /health`.

For quick local development without a Supabase Postgres instance, `DATABASE_URL` can be left as
the SQLite default in `.env.example` (`sqlite:///./beadstore_dev.db`) — SQLAlchemy models avoid
Postgres-only types so the same code runs against either. Use a real Supabase Postgres URL for
anything beyond local iteration.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # edit values, see Environment Variables below
npm run dev -- --port 5193
```

Frontend runs at `http://localhost:5193` and expects the backend at `VITE_API_BASE_URL`
(`http://localhost:8123/api/v1` — already the `.env.example` default).

### Restarting after a reboot

Nothing here needs redoing from scratch after a restart — the venv, `node_modules`, `.env` files,
and local SQLite DB all persist on disk. Just:

```bash
# backend
cd backend
./.venv/bin/uvicorn app.main:app --reload --port 8123     # Scripts/ instead of bin/ on Windows

# frontend (separate terminal)
cd frontend
npm run dev -- --port 5193
```

If a command errors with "command not found" / "No such file or directory," that means the venv
itself is missing or incomplete (e.g. it was deleted, or `pip install` never fully completed last
time) — rerun the full Backend setup above, starting from `pip install -r requirements.txt`. This
does not touch `.env` or the database, only the `.venv` folder's installed packages.

## Troubleshooting

**`pip install` fails with `SSL: CERTIFICATE_VERIFY_FAILED` / "unable to get local issuer
certificate"** — this is a local machine/network issue, not a repo problem. Almost always caused by
a corporate VPN, antivirus, or firewall product doing "HTTPS scanning" (Zscaler, Netskope, some
antivirus web-protection features) that intercepts the connection with its own certificate, which
Python's bundled trust store (`certifi`) doesn't know about. Fastest unblock:

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

This only relaxes certificate checking for those two PyPI hosts, for this one install — it doesn't
change how the app itself talks to Supabase/Etsy/anything else. If you'd rather fix the actual
trust issue instead of working around it, the usual culprit is the machine's intercepting root CA
not being in `certifi`'s bundle — ask whoever manages the machine's antivirus/VPN software for its
root certificate, or look into the `pip-system-certs` package (which makes Python trust the OS
certificate store instead of its own bundled one).

**`./.venv/bin/<something>: No such file or directory` on Windows** — the venv layout is
`.venv/Scripts/` on Windows, not `.venv/bin/`. Use `./.venv/Scripts/alembic`,
`./.venv/Scripts/python`, `./.venv/Scripts/uvicorn`, etc. instead. If the venv is *activated*
(prompt shows `(.venv)`) you can also drop the path entirely and just run `alembic`, `python`,
`uvicorn` — activation puts `Scripts/` on `PATH` for you.

**A previously-activated venv's commands aren't found even though `(.venv)` shows in the
prompt** — activation succeeded but the package itself was never installed (or the venv predates
`requirements.txt` gaining a new dependency). Run `pip install -r requirements.txt` again; it's
safe to re-run and only installs what's missing/outdated.

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
| `CORS_ORIGINS` | Comma-separated allowed frontend origins, e.g. `http://localhost:5193` for local dev |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend API base URL — `http://localhost:8123/api/v1` for local dev |
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
./.venv/bin/python scripts/seed_attribute_picklists.py
```

`seed.py` seeds: product categories (Beads, Findings) with example subtypes, a system "Unknown
Vendor" record (used when a supplier order's vendor isn't known), one demo vendor, one demo
location, and one demo product with an inventory unit.

`seed_attribute_picklists.py` seeds ~350 pick-list values (material, color, size, shape, finish,
manufacturing method, design motif, hole configuration, cut style) and additional
categories/subtypes, sourced from a taxonomy survey of other bead stores — so pick-list dropdowns
have useful suggestions before real inventory exists.

Both are safe to re-run — idempotent.

## Tests

### Backend

```bash
cd backend
./.venv/bin/python -m pytest -q
```

152 tests covering: auth (including the profile-auto-provisioning race condition), product CRUD
and validation, inventory unit CRUD and adjustments, purchase order creation and line validation,
receiving against an existing order (full match, shortage, overage, damaged, substitution,
unresolved, multiple receipts against the same line reconciling cumulatively), retroactive
receiving with no prior order, required-field/numeric-bounds validation across the API, the audit
log's automatic create/update/delete capture, sales recording (FIFO inventory consumption,
insufficient-stock rejection), the storefront-facing API (auth scoping, published-only visibility,
price-tampering resistance), and the Etsy integration (OAuth/PKCE handshake, push/pull sync,
webhook signature verification) driven against the built-in Etsy simulator rather than mocked.

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

One Render **Web Service**, combining both halves: the backend build step also builds the
frontend, and FastAPI serves the built frontend directly (static assets + a client-side-routing
fallback) alongside the `/api/v1/*` endpoints. See `docs/design/render-deployment-guide.md` for
the exact build/start commands, every environment variable, Supabase-side notes, and the tradeoffs
of this single-service approach vs. running the frontend as its own service. Never commit real
secrets to the repo — configure them in the Render dashboard.

## Installable App (PWA)

The frontend ships a minimal web app manifest (`frontend/public/manifest.webmanifest`) and a
static-shell-only service worker (`frontend/public/sw.js`), so once deployed on Render over HTTPS
it can be installed from the browser on a laptop/desktop or added to a phone's home screen. The
service worker only caches the app's own HTML/JS/CSS/icons — it never caches API responses, so no
inventory/product/vendor/order/receipt data is ever stored on the device. There is no offline
support for actual business workflows; installing only changes how the app opens (its own window/
icon instead of a browser tab). See `docs/design/pwa-install-instructions.md` for install/
uninstall steps to share with Patti and Erik.

**Cache versioning:** `npm run build` automatically stamps a fresh, unique cache-version string
into the built `dist/sw.js` (`scripts/stamp-sw-version.mjs`) — the source `public/sw.js` keeps a
placeholder and is never hand-edited per release. The service worker's `activate` handler deletes
any cache that doesn't match the current build's version, so every deploy automatically cleans up
the previous one; nobody has to remember to bump a version number by hand. The backend also
explicitly serves `/sw.js`, `/index.html`, and `/manifest.webmanifest` with
`Cache-Control: no-cache` (see `app/main.py`), so neither the browser nor any intermediary can
serve a stale copy of those specific files regardless of the service worker logic — hashed asset
files under `/assets/` are safe to cache long-term instead, since their filename changes whenever
their content does. The cache-cleanup behavior was verified by simulating two consecutive builds
served from the same URL (mimicking a redeploy): the first build's cache populated as expected,
and after swapping in the second build and forcing an update check, the old cache was fully
deleted and only the new build's cache remained.

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
