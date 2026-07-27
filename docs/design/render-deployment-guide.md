# Render Deployment Guide — Patti Back Office

**One Render Web Service**, combining backend and frontend: the build step builds the React app,
and FastAPI serves the built files directly (static assets + a fallback route for client-side
routing) alongside the `/api/v1/*` API. There is no separate Static Site.

## Why combined, and the tradeoff

This was a deliberate simplicity choice over running two independent Render services (a Web
Service for the API and a Static Site for the frontend). One build, one deploy, one URL, no CORS
configuration needed in production since frontend and API become same-origin.

The cost: Render's Static Sites are served from its CDN and never sleep, regardless of plan.
Combined into one Web Service, the *entire app* — including just loading the login page — now
goes through the free tier's cold-start sleep after ~15 minutes idle. Previously only the backend
API calls were affected by that; now the frontend shell is too. If that first-load delay becomes a
problem once Patti's using this for real, the fix is upgrading the service off the free tier — not
a code change back to the split setup, though reverting to two services is also always an option
if better isolation is wanted later (e.g. if this becomes a multi-tenant SaaS product).

## Render Web Service settings

- Root Directory: repository root (not `backend/` — the build step needs to reach `frontend/` too)
- Build Command:
  ```
  cd frontend && npm install && npm run build && cd ../backend && pip install -r requirements.txt
  ```
- Start Command:
  ```
  cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
  Same two details as always matter here:
  - `--host 0.0.0.0` — Render's proxy can't reach a server bound to `127.0.0.1`.
  - `--port $PORT` — Render assigns the port at runtime; don't hardcode one.
  - Chaining `alembic upgrade head &&` re-runs the migration check on every deploy and every
    cold-start wake — harmless, since it's a no-op once the schema is current.

FastAPI only serves the frontend if it finds a built `frontend/dist` directory next to `backend/`
at startup (see `FRONTEND_DIST` in `app/main.py`) — so this same backend code also runs
unmodified in local dev (where you typically don't bother building the frontend) and in the test
suite, without any special-casing.

## Environment variables

Only the backend service needs configuring now — there's no separate frontend build-time
environment.

| Variable | Value |
|---|---|
| `ENV` | `production` |
| `DATABASE_URL` | Supabase **Session Pooler** connection string, `postgresql://` swapped to `postgresql+psycopg2://`, with the real DB password filled in (see Supabase section below) |
| `SUPABASE_URL` | `https://<your-project-ref>.supabase.co` |
| `SUPABASE_JWT_SECRET` | The legacy JWT secret from Supabase (kept as a fallback; current Supabase projects verify most tokens via JWKS using `SUPABASE_URL` instead) |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `ALLOW_PUBLIC_SIGNUP` | `false` |
| `CORS_ORIGINS` | No longer functionally required (frontend and API are same-origin in production) — safe to leave as-is or set to the service's own URL; it only matters for local dev's split frontend/backend processes |

The frontend's `VITE_*` variables are still needed, but only as **build-time** values baked in
during `npm run build` inside the same Render build step — set them the same way (Render lets you
set environment variables visible to the whole service's build, not just the start command):

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `/api/v1` — a **relative** path now, since frontend and API share an origin. No need to know the service's own URL in advance, which sidesteps the chicken-and-egg problem of not knowing your Render URL until after the first deploy. |
| `VITE_SUPABASE_URL` | Same Supabase project URL as the backend |
| `VITE_SUPABASE_ANON_KEY` | Supabase **anon `public`** key (Project Settings → API → Project API keys) — never the `service_role` key |

Leave `DATABASE_URL_MIGRATIONS` unset — it falls back to `DATABASE_URL` automatically.

## Already handled in the repo, nothing to configure

- SPA fallback (deep-linking/refresh on any client route, e.g. a linked product or order) is
  handled by a catch-all route in `app/main.py`, not a hosting-provider convention file — it
  explicitly returns a real 404 for anything under `/api/` that doesn't match a real API route,
  rather than masking a typo'd API call as a confusing 200 of the app shell.
- `/sw.js`, `/index.html`, and `/manifest.webmanifest` are served with `Cache-Control: no-cache`
  directly by those same FastAPI routes, so a deploy is never masked by stale caching at the HTTP
  layer. Hashed assets under `/assets/` don't need special handling — their filename changes
  whenever their content does.
- `npm run build` automatically stamps a fresh service-worker cache version, so old cached files
  get cleaned up on every deploy (see README "Cache versioning").

## Supabase side

Nothing new needs to be created for this deployment beyond what's already set up for local
testing:
- Same project, same Auth users (Patti/Erik accounts), same database/schema.
- Use the **Session Pooler** connection string (not "Direct connection") for `DATABASE_URL` — the
  direct-connection hostname often only resolves over IPv6, which caused DNS failures during
  local setup; the pooler avoids that.
- No Row Level Security policies need to be added or changed. The backend connects straight to
  Postgres with its own connection string — it doesn't go through Supabase's client/PostgREST
  layer, so table-level RLS (if any exists) isn't in this request path either way.
- **Supabase free-tier projects pause automatically after about a week of no API activity**, and
  don't wake themselves back up — someone has to open the Supabase dashboard and manually resume
  the project. If Patti goes quiet on the app for a while between review sessions, check the
  Supabase dashboard first if things seem broken, before assuming it's a Render or app issue.

## Free-tier sizing (0.1 CPU / 512 MB)

Fine for this app at prototype/review scale — FastAPI + SQLAlchemy under one or two concurrent
users has a very light footprint, and serving a small React static build alongside it doesn't
meaningfully change that. The one behavioral thing worth knowing, expanded on above: the *entire*
app now sleeps after ~15 minutes idle and takes a cold-start (something like 30–60 seconds) to
wake on the next request — not just API calls, since the frontend shell no longer lives on a
never-sleeping CDN. Worth mentioning to Patti up front so a slow first load after a break doesn't
read as broken.
