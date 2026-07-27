"""Seed baseline reference/demo data for local development.

Run with: python -m scripts.seed
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal
from app.models.enums import ActiveArchivedStatus, InventoryUnitStatus, UnitType
from app.models.inventory_unit import InventoryUnit
from app.models.location import Location
from app.models.product import Product
from app.models.product_category import ProductCategory, ProductSubtype
from app.models.vendor import Vendor
from app.services.receiving_service import UNKNOWN_VENDOR_NAME

CATEGORY_SUBTYPES = {
    "Beads": ["Round", "Faceted", "Seed Bead", "Rondelle"],
    "Findings": ["Clasp", "Jump Ring", "Ear Wire", "Crimp"],
}


def run():
    db = SessionLocal()
    try:
        categories = {}
        for name in CATEGORY_SUBTYPES:
            category = db.query(ProductCategory).filter(ProductCategory.name == name).first()
            if category is None:
                category = ProductCategory(name=name)
                db.add(category)
                db.flush()
            categories[name] = category

        subtypes = {}
        for category_name, subtype_names in CATEGORY_SUBTYPES.items():
            category = categories[category_name]
            for subtype_name in subtype_names:
                subtype = (
                    db.query(ProductSubtype)
                    .filter(ProductSubtype.category_id == category.id, ProductSubtype.name == subtype_name)
                    .first()
                )
                if subtype is None:
                    subtype = ProductSubtype(category_id=category.id, name=subtype_name)
                    db.add(subtype)
                    db.flush()
                subtypes[(category_name, subtype_name)] = subtype

        db.commit()

        if db.query(Vendor).filter(Vendor.name == UNKNOWN_VENDOR_NAME).first() is None:
            db.add(Vendor(name=UNKNOWN_VENDOR_NAME))

        demo_vendor = db.query(Vendor).filter(Vendor.name == "Sunrise Bead Supply").first()
        if demo_vendor is None:
            demo_vendor = Vendor(
                name="Sunrise Bead Supply",
                contact_name="Jamie Rivera",
                email="orders@sunrisebeadsupply.example",
            )
            db.add(demo_vendor)
        db.commit()

        default_location = db.query(Location).filter(Location.name == "Front Cabinet").first()
        if default_location is None:
            default_location = Location(name="Front Cabinet", description="Main display cabinet")
            db.add(default_location)
            db.commit()

        demo_product = db.query(Product).filter(Product.name == "6mm Round Faceted Amethyst").first()
        if demo_product is None:
            demo_product = Product(
                name="6mm Round Faceted Amethyst",
                category_id=categories["Beads"].id,
                subtype_id=subtypes[("Beads", "Faceted")].id,
                material="Amethyst",
                color="Purple",
                size="6mm",
                shape="Round",
                status=ActiveArchivedStatus.active,
            )
            db.add(demo_product)
            db.commit()

            db.add(
                InventoryUnit(
                    product_id=demo_product.id,
                    quantity=5,
                    unit_type=UnitType.strand,
                    status=InventoryUnitStatus.available,
                    received_date=datetime.date.today(),
                    vendor_id=demo_vendor.id,
                    location_id=default_location.id,
                )
            )
            db.commit()

        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
