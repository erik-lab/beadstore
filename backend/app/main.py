from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
