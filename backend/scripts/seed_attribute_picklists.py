"""Prepopulate product attribute pick lists and category/subtype reference data.

Source: a bead-taxonomy survey Patti compiled from several other online bead
stores' site maps (product types/attributes only — no product names or
descriptions were imported, per her instruction). This seeds the *pick lists*
(dropdown suggestions) for product attributes, plus categories/subtypes, so
they're populated before real inventory exists. It does not create any
Product rows.

Idempotent — safe to run more than once.

Run with: python -m scripts.seed_attribute_picklists
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal
from app.models.attribute_option import AttributeOption
from app.models.product_category import ProductCategory, ProductSubtype

# --- Attribute pick lists -----------------------------------------------
# Columns that map directly onto existing Product attribute fields.

SHAPE = [
    "Bar", "Barrel", "Beam", "Bellflower", "Bicone", "Brick", "Briolette", "Bugle", "Button",
    "Cabochon", "Candy Kiss", "Chip", "Coin", "Cone", "Crescent", "Cube", "Dagger", "Diamond",
    "Disc", "Drop", "Flower", "Half Moon", "Heart", "Heishi", "Hexagon", "Horn", "Kite", "Leaf",
    "Lentil", "Marquise", "Melon", "Nugget", "Octagon", "Off Round", "Oval", "Pear", "Pentagon",
    "Petal", "Pillow", "Pinch Bead", "Potato", "Pyramid", "Rectangle", "Rice", "Rondelle",
    "Round", "Shield", "Slice", "Spacer", "Spade", "Spike", "Spindle", "Square", "Star",
    "Teardrop", "Thorn", "Triangle", "Trillion", "Tube", "Twist",
]

SIZE = [
    "10-11mm", "10-12mm", "10-15mm", "10mm", "10x10mm", "10x3mm", "10x6mm", "10x8mm", "11-22mm",
    "11mm", "11x6mm", "11x7mm", "11x8-14x11mm", "11x8mm", "11x9mm", "12-15mm", "12-19mm", "12mm",
    "12x10mm", "12x21-15x26mm", "12x6mm", "12x8mm", "12x9mm", "13mm", "13x11mm", "13x12mm",
    "13x13mm", "13x8mm", "13x9mm", "14mm", "14x10mm", "14x11mm", "14x6mm", "14x7mm", "14x8mm",
    "15mm", "15x11mm", "15x12mm", "15x15x15mm", "16 Gauge", "16mm", "16x12mm", "16x14mm",
    "16x5mm", "17-18mm", "17x12mm", "17x14mm", "17x7mm", "18 Gauge", "18mm", "18x11mm", "18x12mm",
    "18x15mm", "19x12mm", "19x9mm", "20 Gauge", "20-33mm", "20mm", "20x12mm", "20x16mm",
    "20x17mm", "22 Gauge", "22mm", "22x11mm", "22x8mm", "23mm", "23x5mm", "24 Gauge", "25x10mm",
    "26 Gauge", "28 Gauge", "34mm+", "3mm", "3x2mm", "4mm", "4x3mm", "5-7mm", "5mm", "5x3mm",
    "5x5mm", "6-8mm", "6mm", "6x4mm", "6x5mm", "6x9mm", "7-10mm", "7-9mm", "7mm", "7x14mm",
    "7x5mm", "8-10mm", "8mm", "8mm+", "8x4mm", "8x6mm", "8x6x3mm", "8x7-20x16mm", "9-11mm", "9mm",
    "9x18mm", "9x6mm", "6/0",
]

MATERIAL = [
    "Acrylic", "Actinolite", "Afghanite", "African Turquoise Jasper", "Agalmatolite", "Agate",
    "Amazonite", "Amber", "Amethyst", "Ametrine", "Ammolite", "Ammonite Fossil", "Andalusite",
    "Andesine", "Angelite", "Apatite", "Aquamarine", "Aragonite", "Aura Quartz", "Auralite",
    "Australian Opal", "Aventurine", "Azurite", "Beryl", "Bi-Colored Quartz", "Biotite",
    "Black Spinel", "Blood Stone", "Bloodstone", "Blue Peruvian Opal", "Bone", "Botswana Agate",
    "Brass", "Bronzite", "Bumblebee Jasper", "Calcite", "Carnelian", "Cat's Eye (Chrysoberyl)",
    "Cat's Eye Quartz", "Cat's Eye Stone", "Celestite", "Chalcedony", "Charoite",
    "Chrome Diopside", "Chrysocolla", "Chrysoprase", "Chrysotine", "Cinnabar", "Citrine",
    "Clear Quartz", "Coal Crystal", "Copper", "Coral", "Coral Fossil", "Corundum",
    "Cubic Zirconia", "Cuprite", "DZi", "Denim Blue Opal", "Diopside", "Dioptase", "Druzy",
    "Dumortierite", "Emerald", "Epidote", "Ethiopian Opal", "Feldspar", "Ferrous Quartz",
    "Fire Opal", "Fluorite", "Fossil", "Freshwater Pearl", "Gabbro", "Garnet", "Glass",
    "GlowStone", "Goldstone", "Green Onyx", "Grossular Garnet", "Hawkeye Stone", "Hematite",
    "Hemimorphite", "Hessonite Garnet", "Hokutolite", "Honey Opal", "Hornblende", "Howlite",
    "Hypersthene", "Idocrase", "Indigo Gabro", "Iolite", "Jade", "Jadeite", "Jasper", "K2",
    "Kunzite", "Kyanite", "Labradorite", "Lapis", "Lapis Lazuli", "Larimar", "Lava", "Lava Stone",
    "Leather", "Lemon Quartz", "Leopardskin Jasper", "Lepidocrocite", "Lepidolite", "Llanite",
    "Lodalite", "Magnesite", "Malachite", "Marble", "Metal", "Mexican Fire Opal", "Moldavite",
    "Mookaite", "Mookaite Jasper", "Moonstone", "Morganite", "Moss Aquamarine", "Mossy Amethyst",
    "Mother of Pearl", "Natrolite", "Natural Chalcedony", "Natural Crystal", "Obsidian",
    "Ocean Jasper", "Onyx", "Opal", "Opalite", "Pearl", "Peridot", "Phlogopite", "Phosphosiderite",
    "Picture Jasper", "Pietersite", "Pink Amethyst", "Pink Peruvian Opal", "Plastic",
    "Polymer Clay", "Porcelain", "Prehnite", "Pyrite", "Quartz", "Quartzite", "Rainbow Moonstone",
    "Rainforest Stone", "Resin", "Rhodochrosite", "Rhodolite Garnet", "Rhodonite", "Rhyolite",
    "Rose Quartz", "Rubber", "Ruby", "Ruby in Zoisite", "Rutilated Quartz", "Sandstone",
    "Sapphire", "Sea Sediment", "Selenite", "Seraphinite", "Serpentine", "Shell", "Shungite",
    "Silver", "Smoky Quartz", "Snowflake Obsidian", "Sodalite", "Solar Quartz",
    "Spessartite Garnet", "Spinel", "Stone Serpentine", "Strawberry Quartz", "Sugilite",
    "Sunstone", "Tanzanian Green Opal", "Tanzanite", "Terahertz Stone", "Thulite", "Tiger Eye",
    "Tiger Eye Stone", "Tiger Iron", "Topaz", "Tourmalinated Quartz", "Tourmaline",
    "Tsavorite Garnet", "Turkish Chalcedony", "Turquoise", "Unakite", "Variscite", "Verdite",
    "Wood", "Zircon", "Zoisite",
]

COLOR = [
    "Black", "Blue", "Brown", "Golden", "Green", "Grey", "Multi Color", "Orange", "Pink",
    "Purple", "Red", "Rose Gold", "White", "Yellow",
]

FINISH = ["Corrugated", "Frosted", "Matte", "Metallic", "Stardust", "Waxed"]

# --- New attribute columns (not previously in the schema) ---------------

MANUFACTURING_METHOD = [
    "Antiqued", "Bezel Set", "Carved", "Embossed", "Enamel Plated", "Faceted",
    "Fire-Polished / Faceted", "Gold Plated", "Hammer Faceted", "Hand Carved", "Hand Cut",
    "Hand Faceted", "Hand Wrapped", "Lampwork", "Laser Etched", "Leafed", "Micro Faceted",
    "Millefiori", "Pressed Glass", "Silver Plated", "Table Cut", "Tumbled", "Wire Wrapped",
]

DESIGN_MOTIF = [
    "Aster", "Bee", "Bird", "Cat", "Chili Pepper", "Coffee Bean", "Cross", "Dice", "Domino",
    "Dragonfly", "Dutch Clog", "Egyptian Cartouche", "Egyptian Cat", "Fish", "Fossil", "Goddess",
    "Greek Key", "Ladybug", "Lotus", "Moon Face", "Nautilus", "Owl", "Pig", "Pine Cone",
    "Quilted", "River", "Scarab", "Snail", "Star", "Starburst", "Sugar Skull", "Sun", "Sunburst",
    "Swallow", "Triangle Motif", "Tree of Life", "Yin Yang",
]

HOLE_CONFIGURATION = [
    "2-Hole", "Alternate Hole", "Center-Drilled", "Corner-Drilled", "Diagonal Hole",
    "Double-Drilled", "Large Hole", "Short Hole", "Side-Drilled", "Straight-Drilled",
    "Top-Drilled",
]

CUT_STYLE = [
    "Central Cut", "Chopped", "Diamond Cut", "Fancy Cut", "Gem Cut", "Grooved", "Pineapple Cut",
    "Saturn Cut", "Scalloped",
]

ATTRIBUTE_OPTIONS = {
    "shape": SHAPE,
    "size": SIZE,
    "material": MATERIAL,
    "color": COLOR,
    "finish": FINISH,
    "manufacturing_method": MANUFACTURING_METHOD,
    "design_motif": DESIGN_MOTIF,
    "hole_configuration": HOLE_CONFIGURATION,
    "cut_style": CUT_STYLE,
}

# --- Categories and subtypes ---------------------------------------------
# "Beads" and "Findings" already exist (see scripts/seed.py); this adds
# subtypes not already present, plus three new categories the source data
# covers. Patti said tools-as-products are off the table for now, so no
# "Tools" category is added even though it wasn't in the source data anyway.

CATEGORY_SUBTYPES = {
    "Beads": [
        "Pressed Glass", "Table Cut", "Firepolished/Faceted", "Czech Glass Beads", "Glass Beads",
    ],
    "Findings": [
        "Stringing Materials", "Wire", "Bails, Cails, & Similar", "Caps, Cones, & Other Ends",
        "Cabochons", "Head Pins", "Leather Findings", "Metal Findings", "Rhinestones",
    ],
    "Chains": [
        "14K Gold Filled", "14K Rose Gold Filled", "Acrylic Chain", "Black Gold Chain",
        "Black Gold Plated Link Chain", "Chain By The Foot", "Dangling Hand Wrapped Chain",
        "Electro-Plated Chain", "Freshwater Pearl Chain by the Foot", "Gemstone Chain",
        "Gold Chain", "Gold Plated Link Chain", "Hand Wrapped Chains", "Metal Link Chain",
        "Rose Gold Plated Link Chain", "Silver Chain", "Silver Plated Link Chain",
        "Stainless Steel", "Sterling Silver",
    ],
    "Charms": [
        "Focal Beads / Pendants / Connectors", "Bezeled Gemstone Pendants And Connectors",
        "Bottle, Capsule, & Container Charms & Pendants",
        "Double Leafed Gemstone Pendants Collection", "Enamel Charms and Pendants",
        "Gemstone Charms & Pendants", "Glass Charms & Pendants", "Hoops",
        "Metal Charms & Pendants", "Multicultural Charms & Pendants", "Pearl Charms & Pendants",
        "Resin Charms & Pendants", "Shell Charms & Pendants", "Tassels",
    ],
    "Clasps": [
        "Lobster Clasps", "Magnetic Clasps", "Toggles And Clasps", "Designer Clasps",
    ],
}


def run():
    db = SessionLocal()
    try:
        categories = {c.name: c for c in db.query(ProductCategory).all()}
        for category_name, subtype_names in CATEGORY_SUBTYPES.items():
            category = categories.get(category_name)
            if category is None:
                category = ProductCategory(name=category_name)
                db.add(category)
                db.flush()
                categories[category_name] = category

            existing_subtypes = {
                s.name
                for s in db.query(ProductSubtype).filter(ProductSubtype.category_id == category.id).all()
            }
            for subtype_name in subtype_names:
                if subtype_name in existing_subtypes:
                    continue
                db.add(ProductSubtype(category_id=category.id, name=subtype_name))
        db.commit()

        for field, values in ATTRIBUTE_OPTIONS.items():
            existing_values = {
                o.value for o in db.query(AttributeOption).filter(AttributeOption.field == field).all()
            }
            for value in values:
                if value in existing_values:
                    continue
                db.add(AttributeOption(field=field, value=value))
        db.commit()

        print("Attribute pick list seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
