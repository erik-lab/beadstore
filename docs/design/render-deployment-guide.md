# Render Deployment Guide — Patti Back Office

Two Render services: a **Web Service** for the backend, a **Static Site** for the frontend.

## Backend — Web Service

**Settings:**
- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command:
  ```
  alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
  Two details matter here and are easy to miss:
  - `--host 0.0.0.0` — Render's health checks/proxy can't reach a server bound to `127.0.0.1`.
  - `--port $PORT` — Render assigns the port at runtime via the `$PORT` env var; a hardcoded
    port (like the `8123` used for local dev) will fail health checks in production.
  - Chaining `alembic upgrade head &&` re-runs the migration check on every deploy and every
    cold-start wake. That's intentional and harmless — Alembic is a no-op once the schema is
    current — and it means you never have to remember a separate manual migration step.

**Environment variables:**

| Variable | Value |
|---|---|
| `ENV` | `production` |
| `DATABASE_URL` | Supabase **Session Pooler** connection string, `postgresql://` swapped to `postgresql+psycopg2://`, with the real DB password filled in (see Supabase section below) |
| `SUPABASE_URL` | `https://<your-project-ref>.supabase.co` |
| `SUPABASE_JWT_SECRET` | The legacy JWT secret from Supabase (kept as a fallback; current Supabase projects verify most tokens via JWKS using `SUPABASE_URL` instead — see note below) |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `ALLOW_PUBLIC_SIGNUP` | `false` |
| `CORS_ORIGINS` | The frontend's exact Render URL, e.g. `https://patti-back-office.onrender.com` (no trailing slash) |

Leave `DATABASE_URL_MIGRATIONS` unset — it falls back to `DATABASE_URL` automatically.

## Frontend — Static Site

**Settings:**
- Root Directory: `frontend`
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`

**Environment variables** (these are baked into the JS bundle **at build time** — changing one
requires a rebuild/redeploy, not just an env var edit, since a static site has no running process
to pick up a change):

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | The backend's exact Render URL + `/api/v1`, e.g. `https://patti-back-office-api.onrender.com/api/v1` |
| `VITE_SUPABASE_URL` | Same Supabase project URL as the backend |
| `VITE_SUPABASE_ANON_KEY` | Supabase **anon `public`** key (Project Settings → API → Project API keys) — never the `service_role` key |

**Already handled in the repo, nothing to configure:**
- `frontend/public/_redirects` rewrites every path to `index.html` — required because this is a
  client-side-routed React app; without it, refreshing or directly opening any URL other than `/`
  (e.g. a link to a specific product or order) would 404 on a static host.
- `frontend/public/_headers` sets `no-cache` on `/sw.js`, `/index.html`, and
  `/manifest.webmanifest` so neither Render's CDN nor the browser serves a stale shell after a
  deploy, while hashed JS/CSS assets stay long-cached.
- `npm run build` automatically stamps a fresh service-worker cache version, so old cached files
  get cleaned up on every deploy (see README "Cache versioning").

## Supabase side

Nothing new needs to be created for deployment beyond what's already set up for local testing:
- Same project, same Auth users (Patti/Erik accounts), same database/schema.
- Use the **Session Pooler** connection string (not "Direct connection") for `DATABASE_URL` — the
  direct-connection hostname often only resolves over IPv6, which caused the DNS failures during
  local setup; the pooler avoids that.
- No Row Level Security policies need to be added or changed. The backend connects straight to
  Postgres with its own connection string — it doesn't go through Supabase's client/PostgREST
  layer, so table-level RLS (if any exists) isn't in this request path either way.
- **Supabase free-tier projects pause automatically after about a week of no API activity**, and
  don't wake themselves back up — someone has to open the Supabase dashboard and manually resume
  the project. If Patti goes quiet on the app for a while between review sessions, check the
  Supabase dashboard first if things seem broken, before assuming it's a Render or app issue.

## Free-tier sizing (0.1 CPU / 512 MB)

This is fine for the backend at prototype/review scale — FastAPI + SQLAlchemy under one or two
concurrent users has a very light footprint, and the app holds no in-memory state that would
grow with usage. Two things worth knowing going in, both about *behavior*, not capacity:

1. **The backend (Web Service) sleeps after ~15 minutes idle** on Render's free tier, and the next
   request wakes it — a cold start that can take something like 30–60 seconds. If Patti opens the
   app after a break, the first screen may sit "loading" longer than expected before anything
   past login responds. This is expected free-tier behavior, not a bug; worth mentioning to her
   up front so it doesn't read as broken. If that first-load delay is a problem for how you want
   the review to go, the fix is upgrading the backend service off the free tier — not a code
   change.
2. **The frontend (Static Site) does not sleep** — Render serves static sites from its CDN
   regardless of plan, so the app shell always loads instantly; only backend API calls are
   affected by the above.

Nothing about the free tier's CPU/RAM limits themselves is a concern for this app at this stage.
