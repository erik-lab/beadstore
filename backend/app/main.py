from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import (
    auth,
    catalog_listings,
    dashboard,
    inventory_units,
    locations,
    product_categories,
    products,
    purchase_orders,
    receiving,
    vendors,
)

settings = get_settings()

app = FastAPI(title="Patti Back Office API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(vendors.router, prefix="/api/v1")
app.include_router(product_categories.router, prefix="/api/v1")
app.include_router(product_categories.subtype_router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(catalog_listings.router, prefix="/api/v1")
app.include_router(inventory_units.router, prefix="/api/v1")
app.include_router(locations.router, prefix="/api/v1")
app.include_router(purchase_orders.router, prefix="/api/v1")
app.include_router(receiving.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


# Serve the built frontend from this same service, so one Render Web Service
# hosts both. Gated on the built directory actually existing so a
# backend-only checkout (local API dev, the test suite, CI) is unaffected —
# nothing below runs unless `npm run build` has produced `frontend/dist`.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}

    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")
    app.mount("/icons", StaticFiles(directory=FRONTEND_DIST / "icons"), name="frontend-icons")

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "favicon.svg")

    @app.get("/icons.svg", include_in_schema=False)
    def icons_svg() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "icons.svg")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest() -> FileResponse:
        return FileResponse(
            FRONTEND_DIST / "manifest.webmanifest",
            media_type="application/manifest+json",
            headers=NO_CACHE_HEADERS,
        )

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        # Never cache the service worker script itself — see
        # scripts/stamp-sw-version.mjs and the "Cache versioning" section of
        # the README for why this matters for picking up new deploys.
        return FileResponse(FRONTEND_DIST / "sw.js", media_type="text/javascript", headers=NO_CACHE_HEADERS)

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str = "") -> FileResponse:
        # Client-side routing (React Router) owns everything not already
        # matched above by an API route or a static file — reject anything
        # that looks like a misrouted API call instead of masking it as a
        # confusing 200 of the app shell.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        return FileResponse(FRONTEND_DIST / "index.html", headers=NO_CACHE_HEADERS)
