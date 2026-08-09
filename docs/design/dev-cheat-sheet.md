# Beadstore Dev Cheat-Sheet

Quick reference for this project specifically — ports are set non-default here to avoid
collisions with your other projects running at the same time.

## Ports (this project)

| Service | Port | Default (unused here) |
|---|---|---|
| Backend (uvicorn) | **8123** | 8000 |
| Frontend (Vite)   | **5193** | 5173 |

## Start servers

```bash
# backend
cd backend
./.venv/bin/uvicorn app.main:app --reload --port 8123

# frontend
cd frontend
npm run dev -- --port 5193
```

Frontend's `VITE_API_BASE_URL` in `frontend/.env` needs to point at
`http://localhost:8123/api/v1` for the two to talk to each other locally.

## Stop a stray process on a port

```bash
lsof -i :8123          # find it
kill -TERM <pid>        # graceful
# or by name
pkill -f uvicorn
pkill -f gunicorn
```

## Common commands

```bash
# run tests
cd backend && ./.venv/bin/python -m pytest -q

# frontend build/typecheck gate
cd frontend && npm run build

# apply DB migrations
cd backend && ./.venv/bin/python -m alembic upgrade head

# seed reference/demo data (idempotent)
cd backend && ./.venv/bin/python -m scripts.seed
cd backend && ./.venv/bin/python -m scripts.seed_attribute_picklists
```

## Deploy branch

Working branch: `claude/new-app-development-plan-njjwt7`

```bash
git push -u origin claude/new-app-development-plan-njjwt7
```

Render auto-runs `alembic upgrade head` on deploy (see start command in
`docs/design/render-deployment-guide.md`). One-off scripts (like the picklist
seed) still need to be run manually against prod after a deploy — see that
doc's "Render" section for how.

## Where things live

- Deployment details (Render settings, env vars, Supabase notes): `docs/design/render-deployment-guide.md`
- Architecture/schema notes: `docs/design/mvp-technical-design.md`
- This file: update it whenever ports/commands change so it doesn't go stale.
