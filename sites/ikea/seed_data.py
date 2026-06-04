"""Deterministic seed data and local SVG asset generation for the IKEA demo."""
from __future__ import annotations

import os
import random
import shutil
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

from app import (  # noqa: E402
    BASE_DIR,
    DB_PATH,
    CartItem,
    Category,
    CompareItem,
    Deal,
    DeliveryOption,
    Order,
    OrderItem,
    PaymentMock,
    PickupSlot,
    Product,
    ProtectionPlan,
    RewardActivity,
    RoomBundle,
    Store,
    StoreInventory,
    SupportArticle,
    SupportTicket,
    User,
    WishlistItem,
    app,
    db,
    dumps_json,
)
from app import Review  # noqa: E402
from app import ROOM_LABELS  # noqa: E402

RNG = random.Random(20260604)
STATIC_IMAGES = BASE_DIR / "static" / "images"
INSTANCE_SEED_DIR = BASE_DIR / "instance_seed"

CATEGORY_DATA = [
    ("living-room-seating", "Living room seating", "living-room", "Modular sofas, nesting tables, and relaxed seating built for everyday lounging."),
    ("bedroom-storage", "Bedroom storage", "bedroom", "Beds, dressers, and wardrobes that keep calm routines on schedule."),
    ("kitchen-dining", "Kitchen & dining", "kitchen", "Tables, chairs, and smart carts sized for shared meals and small spaces."),
    ("home-office", "Home office", "office", "Desks, seating, and organizers for focused work-from-home setups."),
    ("lighting", "Lighting", "lighting", "Layered task, floor, and pendant lighting for brighter rooms."),
    ("bathroom", "Bathroom", "bathroom", "Vanities, caddies, mirrors, and textile helpers for small baths."),
    ("kids-room", "Children's room", "kids", "Toy storage, activity furniture, and sleep essentials sized for families."),
    ("outdoor-living", "Outdoor living", "outdoor", "Patio seating, balcony dining, and weather-tough storage."),
    ("entryway", "Entryway", "entryway", "Hooks, benches, shoe storage, and compact drop zones."),
    ("textiles-rugs", "Textiles & rugs", "textiles", "Rugs, curtains, throws, and cushion layers for warmth and softness."),
    ("storage-organization", "Storage & organization", "storage", "Shelving, bins, rails, and carts that keep clutter sorted."),
    ("decor-mirrors", "Decor & mirrors", "decor", "Mirrors, planters, wall accents, and finishing touches for every room."),
]

STORE_DATA = [
    ("IKEA Brooklyn", "brooklyn-ny", "Brooklyn", "NY", "1 Beard Street, Brooklyn, NY 11231"),
    ("IKEA Burbank", "burbank-ca", "Burbank", "CA", "600 S Ikea Way, Burbank, CA 91502"),
    ("IKEA Schaumburg", "schaumburg-il", "Schaumburg", "IL", "1800 E McConnor Pkwy, Schaumburg, IL 60173"),
    ("IKEA Renton", "renton-wa", "Renton", "WA", "601 SW 41st Street, Renton, WA 98057"),
    ("IKEA Stoughton", "stoughton-ma", "Stoughton", "MA", "1 Ikea Way, Stoughton, MA 02072"),
    ("IKEA Atlanta", "atlanta-ga", "Atlanta", "GA", "441 16th Street NW, Atlanta, GA 30363"),
    ("IKEA Round Rock", "round-rock-tx", "Round Rock", "TX", "1 Ikea Way, Round Rock, TX 78664"),
    ("IKEA Sunrise", "sunrise-fl", "Sunrise", "FL", "151 NW 136th Avenue, Sunrise, FL 33325"),
    ("IKEA Paramus", "paramus-nj", "Paramus", "NJ", "100 Ikea Drive, Paramus, NJ 07652"),
    ("IKEA Conshohocken", "conshohocken-pa", "Conshohocken", "PA", "2206 Chemical Road, Conshohocken, PA 19428"),
    ("IKEA Portland", "portland-or", "Portland", "OR", "10280 NE Cascades Pkwy, Portland, OR 97220"),
    ("IKEA Tempe", "tempe-az", "Tempe", "AZ", "2110 W Ikea Way, Tempe, AZ 85284"),
    ("IKEA Minneapolis", "minneapolis-mn", "Minneapolis", "MN", "8000 Ikea Way, Bloomington, MN 55425"),
    ("IKEA San Diego", "san-diego-ca", "San Diego", "CA", "2149 Fenton Pkwy, San Diego, CA 92108"),
    ("IKEA Charlotte", "charlotte-nc", "Charlotte", "NC", "8300 Ikea Blvd, Charlotte, NC 28262"),
]

SERIES = [
    "BJORNA", "LINDMO", "VALLTORP", "HAVSBERG", "NORDHAV", "LAGKAPTEN",
    "KLARNA", "SOLVIK", "RYTM", "FJARNA", "HEMLUND", "SKOGEN",
    "GLANSA", "SANDVIK", "TROFASTA", "MALARO", "VIKSTEN", "ELDMARK",
]

COLORS = [
    "Birch", "Oak", "White", "Warm beige", "Forest green", "Slate blue",
    "Charcoal", "Soft gray", "Yellow stripe", "Rust red", "Natural pine",
]

MATERIALS = [
    "Solid pine", "Ash veneer", "Steel", "Powder-coated steel", "Cotton blend",
    "Wool mix", "Bamboo", "Tempered glass", "Particleboard", "Birch veneer",
]

SPECIAL_PRODUCTS = [
    {"sku": "IK-10001", "name": "HEMLUND modular sofa", "series": "HEMLUND", "category_slug": "living-room-seating", "room_slug": "living-room", "price": 799.0, "list_price": 899.0, "material": "Cotton blend", "color": "Forest green", "dimensions": "118\" W x 37\" D x 32\" H", "assembly": "Two-person setup", "tags": ["modular", "chaise", "washable cover"], "specs": {"Seats": "4", "Cover": "Removable", "Frame": "Kiln-dried pine", "Depth": "37 in", "Width": "118 in"}, "featured": True, "deal": True},
    {"sku": "IK-10002", "name": "BJORNA lift-top coffee table", "series": "BJORNA", "category_slug": "living-room-seating", "room_slug": "living-room", "price": 229.0, "list_price": 279.0, "material": "Ash veneer", "color": "Oak", "dimensions": "47\" W x 24\" D x 18\" H", "assembly": "Quick setup", "tags": ["storage", "oak", "living room"], "specs": {"Lift top": "Yes", "Storage shelf": "Dual compartment", "Width": "47 in", "Depth": "24 in", "Finish": "Matte oak"}, "featured": True, "deal": False},
    {"sku": "IK-10003", "name": "NORDHAV storage bed frame", "series": "NORDHAV", "category_slug": "bedroom-storage", "room_slug": "bedroom", "price": 649.0, "list_price": 749.0, "material": "Birch veneer", "color": "Warm beige", "dimensions": "84\" W x 87\" D x 45\" H", "assembly": "Weekend setup", "tags": ["queen", "under-bed drawers", "bedroom"], "specs": {"Size": "Queen", "Drawers": "4", "Headboard": "Integrated shelf", "Width": "84 in", "Depth": "87 in"}, "featured": True, "deal": True},
    {"sku": "IK-10004", "name": "NORDHAV 6-drawer dresser", "series": "NORDHAV", "category_slug": "bedroom-storage", "room_slug": "bedroom", "price": 379.0, "list_price": 429.0, "material": "Particleboard", "color": "White", "dimensions": "63\" W x 19\" D x 31\" H", "assembly": "Quick setup", "tags": ["dresser", "6 drawers", "white"], "specs": {"Drawers": "6", "Soft close": "Yes", "Width": "63 in", "Depth": "19 in", "Height": "31 in"}, "featured": False, "deal": False},
    {"sku": "IK-10005", "name": "FJARNA extendable dining table", "series": "FJARNA", "category_slug": "kitchen-dining", "room_slug": "kitchen", "price": 499.0, "list_price": 569.0, "material": "Solid pine", "color": "Natural pine", "dimensions": "71-94\" W x 35\" D x 30\" H", "assembly": "Two-person setup", "tags": ["extendable", "dining table", "seats 6-8"], "specs": {"Seats": "6-8", "Extension leaves": "2", "Width": "71-94 in", "Top": "Solid pine", "Care": "Easy-wipe lacquer"}, "featured": True, "deal": True},
    {"sku": "IK-10006", "name": "FJARNA spindle dining chair", "series": "FJARNA", "category_slug": "kitchen-dining", "room_slug": "kitchen", "price": 89.0, "list_price": 109.0, "material": "Solid pine", "color": "Birch", "dimensions": "18\" W x 20\" D x 35\" H", "assembly": "Quick setup", "tags": ["chair", "dining", "birch"], "specs": {"Seat height": "18 in", "Stackable": "No", "Frame": "Solid pine", "Width": "18 in", "Depth": "20 in"}, "featured": False, "deal": False},
    {"sku": "IK-10007", "name": "LAGKAPTEN sit-stand desk", "series": "LAGKAPTEN", "category_slug": "home-office", "room_slug": "office", "price": 459.0, "list_price": 499.0, "material": "Powder-coated steel", "color": "White", "dimensions": "55\" W x 27\" D x 25-50\" H", "assembly": "Weekend setup", "tags": ["desk", "adjustable", "cable management"], "specs": {"Height range": "25-50 in", "Cable tray": "Included", "Width": "55 in", "Depth": "27 in", "Memory presets": "4"}, "featured": True, "deal": False},
    {"sku": "IK-10008", "name": "LAGKAPTEN ergonomic swivel chair", "series": "LAGKAPTEN", "category_slug": "home-office", "room_slug": "office", "price": 219.0, "list_price": 259.0, "material": "Steel", "color": "Charcoal", "dimensions": "27\" W x 27\" D x 47\" H", "assembly": "Quick setup", "tags": ["ergonomic", "mesh", "office"], "specs": {"Lumbar support": "Adjustable", "Tilt lock": "Yes", "Seat height": "17-22 in", "Material": "Mesh back", "Weight limit": "275 lb"}, "featured": False, "deal": False},
    {"sku": "IK-10009", "name": "SMYCKA arc floor lamp", "series": "SMYCKA", "category_slug": "lighting", "room_slug": "lighting", "price": 149.0, "list_price": 179.0, "material": "Steel", "color": "Slate blue", "dimensions": "18\" W x 68\" D x 83\" H", "assembly": "Quick setup", "tags": ["floor lamp", "reading", "living room"], "specs": {"Bulb base": "E26", "Dimmable": "Yes", "Cord length": "96 in", "Reach": "68 in", "Shade": "Metal"}, "featured": True, "deal": False},
    {"sku": "IK-10010", "name": "SMYCKA pendant cluster lamp", "series": "SMYCKA", "category_slug": "lighting", "room_slug": "lighting", "price": 189.0, "list_price": 229.0, "material": "Tempered glass", "color": "Warm beige", "dimensions": "21\" W x 21\" D x 54\" H", "assembly": "Two-person setup", "tags": ["pendant", "kitchen island", "glass"], "specs": {"Bulbs": "3", "Dimmable": "Yes", "Cord drop": "Adjustable", "Diameter": "21 in", "Shade": "Hand-blown glass"}, "featured": False, "deal": True},
    {"sku": "IK-10011", "name": "KLARNA rolling vanity cart", "series": "KLARNA", "category_slug": "bathroom", "room_slug": "bathroom", "price": 79.0, "list_price": 99.0, "material": "Steel", "color": "Soft gray", "dimensions": "19\" W x 14\" D x 31\" H", "assembly": "Quick setup", "tags": ["bath cart", "wheels", "storage"], "specs": {"Shelves": "3", "Wheels": "4 locking", "Width": "19 in", "Depth": "14 in", "Finish": "Moisture resistant"}, "featured": False, "deal": False},
    {"sku": "IK-10012", "name": "KLARNA mirror cabinet", "series": "KLARNA", "category_slug": "bathroom", "room_slug": "bathroom", "price": 179.0, "list_price": 209.0, "material": "Bamboo", "color": "Natural pine", "dimensions": "24\" W x 6\" D x 30\" H", "assembly": "Quick setup", "tags": ["mirror cabinet", "bathroom", "storage"], "specs": {"Shelves": "4", "Door": "Soft close", "Width": "24 in", "Depth": "6 in", "Finish": "Sealed bamboo"}, "featured": False, "deal": False},
    {"sku": "IK-10013", "name": "TROFASTA toy storage bench", "series": "TROFASTA", "category_slug": "kids-room", "room_slug": "kids", "price": 139.0, "list_price": 169.0, "material": "Particleboard", "color": "Yellow stripe", "dimensions": "35\" W x 17\" D x 20\" H", "assembly": "Quick setup", "tags": ["toy storage", "kids", "bench"], "specs": {"Bins": "4 removable", "Seat height": "20 in", "Width": "35 in", "Depth": "17 in", "Safety": "Rounded edges"}, "featured": True, "deal": False},
    {"sku": "IK-10014", "name": "TROFASTA loft activity table", "series": "TROFASTA", "category_slug": "kids-room", "room_slug": "kids", "price": 169.0, "list_price": 199.0, "material": "Solid pine", "color": "White", "dimensions": "47\" W x 23\" D x 20\" H", "assembly": "Weekend setup", "tags": ["activity table", "storage", "kids"], "specs": {"Seat count": "2", "Bins": "6 integrated", "Width": "47 in", "Depth": "23 in", "Surface": "Easy-clean laminate"}, "featured": False, "deal": True},
    {"sku": "IK-10015", "name": "SKOGEN balcony lounge set", "series": "SKOGEN", "category_slug": "outdoor-living", "room_slug": "outdoor", "price": 429.0, "list_price": 499.0, "material": "Powder-coated steel", "color": "Forest green", "dimensions": "Loveseat + table set", "assembly": "Weekend setup", "tags": ["patio", "outdoor", "2-seat"], "specs": {"Pieces": "3", "Cushions": "Water-repellent", "Stackable chairs": "Yes", "Frame": "Powder-coated steel", "Cover": "Machine washable"}, "featured": True, "deal": True},
    {"sku": "IK-10016", "name": "MALARO weatherproof storage bench", "series": "MALARO", "category_slug": "outdoor-living", "room_slug": "outdoor", "price": 219.0, "list_price": 259.0, "material": "Bamboo", "color": "Charcoal", "dimensions": "48\" W x 21\" D x 22\" H", "assembly": "Quick setup", "tags": ["storage bench", "outdoor", "weatherproof"], "specs": {"Capacity": "47 gal", "Seat count": "2", "Width": "48 in", "Depth": "21 in", "Lid support": "Hydraulic"}, "featured": False, "deal": False},
    {"sku": "IK-10017", "name": "VALLTORP shoe cabinet", "series": "VALLTORP", "category_slug": "entryway", "room_slug": "entryway", "price": 169.0, "list_price": 199.0, "material": "Particleboard", "color": "Warm beige", "dimensions": "31\" W x 10\" D x 50\" H", "assembly": "Quick setup", "tags": ["entryway", "shoe storage", "narrow"], "specs": {"Pairs": "12", "Depth": "10 in", "Width": "31 in", "Wall anchor": "Included", "Ventilation": "Rear panel"}, "featured": True, "deal": False},
    {"sku": "IK-10018", "name": "VALLTORP hallway bench", "series": "VALLTORP", "category_slug": "entryway", "room_slug": "entryway", "price": 129.0, "list_price": 149.0, "material": "Ash veneer", "color": "Oak", "dimensions": "39\" W x 16\" D x 19\" H", "assembly": "Quick setup", "tags": ["bench", "entryway", "oak"], "specs": {"Storage shelf": "Slatted", "Width": "39 in", "Depth": "16 in", "Seat height": "19 in", "Finish": "Matte oak"}, "featured": False, "deal": False},
    {"sku": "IK-10019", "name": "GLANSA handwoven area rug", "series": "GLANSA", "category_slug": "textiles-rugs", "room_slug": "textiles", "price": 199.0, "list_price": 239.0, "material": "Wool mix", "color": "Rust red", "dimensions": "6'7\" x 9'10\"", "assembly": "No assembly", "tags": ["rug", "handwoven", "living room"], "specs": {"Pile": "Low", "Reversible": "Yes", "Material": "Wool mix", "Size": "6'7\" x 9'10\"", "Care": "Vacuum only"}, "featured": True, "deal": True},
    {"sku": "IK-10020", "name": "GLANSA blackout curtain pair", "series": "GLANSA", "category_slug": "textiles-rugs", "room_slug": "textiles", "price": 69.0, "list_price": 85.0, "material": "Cotton blend", "color": "Slate blue", "dimensions": "57\" x 98\"", "assembly": "No assembly", "tags": ["curtains", "blackout", "bedroom"], "specs": {"Panels": "2", "Header": "Hidden tabs", "Length": "98 in", "Width": "57 in", "Light block": "95%"}, "featured": False, "deal": False},
    {"sku": "IK-10021", "name": "RYTM steel shelving unit", "series": "RYTM", "category_slug": "storage-organization", "room_slug": "storage", "price": 149.0, "list_price": 179.0, "material": "Powder-coated steel", "color": "Charcoal", "dimensions": "33\" W x 16\" D x 71\" H", "assembly": "Quick setup", "tags": ["shelving", "steel", "storage"], "specs": {"Shelves": "5", "Adjustable feet": "Yes", "Width": "33 in", "Depth": "16 in", "Weight limit": "110 lb per shelf"}, "featured": True, "deal": False},
    {"sku": "IK-10022", "name": "RYTM utility cart", "series": "RYTM", "category_slug": "storage-organization", "room_slug": "storage", "price": 59.0, "list_price": 75.0, "material": "Steel", "color": "Soft gray", "dimensions": "18\" W x 14\" D x 31\" H", "assembly": "Quick setup", "tags": ["cart", "utility", "rolling"], "specs": {"Shelves": "3", "Wheels": "4", "Width": "18 in", "Depth": "14 in", "Finish": "Powder coated"}, "featured": False, "deal": True},
    {"sku": "IK-10023", "name": "KLARGLA arched floor mirror", "series": "KLARGLA", "category_slug": "decor-mirrors", "room_slug": "decor", "price": 189.0, "list_price": 229.0, "material": "Steel", "color": "Black", "dimensions": "28\" W x 68\" H", "assembly": "No assembly", "tags": ["mirror", "arched", "decor"], "specs": {"Mounting": "Lean or wall-mount", "Width": "28 in", "Height": "68 in", "Frame": "Powder-coated steel", "Finish": "Matte black"}, "featured": True, "deal": False},
    {"sku": "IK-10024", "name": "KLARGLA planter stand trio", "series": "KLARGLA", "category_slug": "decor-mirrors", "room_slug": "decor", "price": 89.0, "list_price": 109.0, "material": "Steel", "color": "Birch", "dimensions": "Set of 3", "assembly": "Quick setup", "tags": ["planter", "decor", "set"], "specs": {"Pieces": "3", "Outdoor safe": "Covered use", "Material": "Steel and birch", "Tallest height": "28 in", "Tray diameter": "12 in"}, "featured": False, "deal": False},
]


def slugify(text: str) -> str:
    return (
        text.lower()
        .replace("&", "and")
        .replace("'", "")
        .replace('"', "")
        .replace(" ", "-")
    )


def svg_card(path: Path, title: str, subtitle: str, bg: str, accent: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" viewBox="0 0 960 720">
<rect width="960" height="720" rx="28" fill="{bg}"/>
<rect x="48" y="52" width="864" height="616" rx="24" fill="white" opacity="0.92"/>
<rect x="88" y="110" width="334" height="334" rx="32" fill="{accent}" opacity="0.14"/>
<circle cx="255" cy="279" r="108" fill="{accent}" opacity="0.28"/>
<rect x="167" y="238" width="176" height="110" rx="18" fill="{accent}" opacity="0.64"/>
<rect x="542" y="170" width="250" height="20" rx="10" fill="{accent}" opacity="0.34"/>
<rect x="542" y="212" width="198" height="18" rx="9" fill="{accent}" opacity="0.18"/>
<rect x="542" y="252" width="154" height="18" rx="9" fill="{accent}" opacity="0.18"/>
<text x="88" y="520" fill="#111827" font-family="Arial, sans-serif" font-size="44" font-weight="700">{title}</text>
<text x="88" y="574" fill="#4b5563" font-family="Arial, sans-serif" font-size="28">{subtitle}</text>
<text x="88" y="628" fill="#4b5563" font-family="Arial, sans-serif" font-size="24">Local benchmark mirror asset</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def category_palette(index: int) -> tuple[str, str]:
    backgrounds = ["#f6f6ef", "#f5efe5", "#eaf2ff", "#eef7ea", "#fff4df", "#f0efff"]
    accents = ["#0058a3", "#f2b632", "#2b5d82", "#2f6f4f", "#b45309", "#5046e5"]
    return backgrounds[index % len(backgrounds)], accents[index % len(accents)]


def build_categories() -> list[Category]:
    categories: list[Category] = []
    for idx, (slug, name, room_slug, description) in enumerate(CATEGORY_DATA):
        categories.append(
            Category(
                slug=slug,
                name=name,
                room_slug=room_slug,
                description=description,
                hero_caption=f"Built for the {room_slug.replace('-', ' ')} routines in this local demo.",
                icon_name=slug.split("-")[0],
            )
        )
        bg, accent = category_palette(idx)
        svg_card(STATIC_IMAGES / "categories" / f"{slug}.svg", name, ROOM_LABELS[room_slug], bg, accent)
    return categories


def build_stores() -> list[Store]:
    stores: list[Store] = []
    for idx, (name, slug, city, state, address) in enumerate(STORE_DATA):
        stores.append(
            Store(
                name=name,
                slug=slug,
                city=city,
                state=state,
                address=address,
                phone=f"(555) 01{idx:02d}-{2000 + idx}",
                hours="10:00 AM - 9:00 PM",
                amenities_json=dumps_json([
                    "Swedish Restaurant",
                    "Click & collect",
                    "Planning studio",
                    "Family member lane",
                ][0 : 2 + (idx % 3)]),
                services_json=dumps_json([
                    "Assembly planning",
                    "Kitchen consultation",
                    "Returns desk",
                    "Large item loading",
                ][0 : 2 + (idx % 2)]),
                image_path=f"images/stores/{slug}.svg",
                pickup_note="Most furniture orders are ready within 4 hours in this demo.",
            )
        )
        bg, accent = category_palette(idx)
        svg_card(STATIC_IMAGES / "stores" / f"{slug}.svg", name, f"{city}, {state}", bg, accent)
    return stores


def product_record(index: int, category_slug: str, room_slug: str, base_name: str) -> dict:
    series = SERIES[index % len(SERIES)]
    color = COLORS[index % len(COLORS)]
    material = MATERIALS[index % len(MATERIALS)]
    width = 24 + (index % 8) * 6
    depth = 14 + (index % 5) * 4
    height = 18 + (index % 9) * 5
    price = round(59 + (index % 13) * 28 + (index % 4) * 9, 2)
    list_price = round(price + 15 + (index % 5) * 7, 2)
    return {
        "sku": f"IK-{11001 + index:05d}",
        "name": f"{series} {base_name}",
        "series": series,
        "category_slug": category_slug,
        "room_slug": room_slug,
        "price": price,
        "list_price": list_price,
        "material": material,
        "color": color,
        "dimensions": f"{width}\" W x {depth}\" D x {height}\" H",
        "assembly": ["Quick setup", "Weekend setup", "Two-person setup"][index % 3],
        "tags": [base_name.split()[0].lower(), room_slug, color.lower(), material.split()[0].lower()],
        "specs": {
            "Width": f"{width} in",
            "Depth": f"{depth} in",
            "Height": f"{height} in",
            "Material": material,
            "Color": color,
        },
        "featured": index % 9 == 0,
        "deal": index % 7 == 0,
    }


def build_products() -> list[Product]:
    categories = {slug: room_slug for slug, _name, room_slug, _desc in CATEGORY_DATA}
    base_names = {
        "living-room-seating": ["3-seat sofa", "storage ottoman", "accent chair", "coffee table", "side table", "media bench", "console table", "daybed", "loveseat", "sleeper sofa", "chaise lounge", "nesting table", "sofa table"],
        "bedroom-storage": ["nightstand", "wardrobe", "dresser", "bedside bench", "platform bed", "storage chest", "underbed box", "headboard shelf", "mirror door wardrobe", "linen chest", "bed frame", "dresser topper", "bed tray"],
        "kitchen-dining": ["bar stool", "serving cart", "dining chair", "drop-leaf table", "sideboard", "baker rack", "kitchen island", "counter stool", "bench seat", "tray table", "dinnerware shelf", "extendable table", "dish cart"],
        "home-office": ["writing desk", "task chair", "bookcase", "drawer unit", "monitor riser", "desk shelf", "printer cabinet", "filing cart", "laptop stand", "desk lamp", "wall organizer", "storage bench", "corner desk"],
        "lighting": ["table lamp", "pendant lamp", "wall light", "floor uplight", "reading lamp", "lantern", "spotlight bar", "ceiling fixture", "picture light", "desk lamp", "led strip", "bedside lamp", "task lamp"],
        "bathroom": ["ladder shelf", "mirror shelf", "towel stand", "laundry hamper", "vanity stool", "shower caddy", "bath mat set", "wall cabinet", "sink trolley", "toilet shelf", "soap tray set", "bath bench", "mirror"],
        "kids-room": ["book ledge", "play table", "canopy bed", "storage cart", "step stool", "art cart", "reading nook chair", "wardrobe", "toy bin", "night light", "desk", "peg rail", "play rug"],
        "outdoor-living": ["dining set", "stackable chair", "balcony table", "planter bench", "sun lounger", "outdoor rug", "storage table", "serving trolley", "shade umbrella", "planter shelf", "patio lamp", "adirondack chair", "bistro table"],
        "entryway": ["coat rack", "umbrella stand", "key shelf", "mail organizer", "narrow bench", "drawer console", "mirror shelf", "boot tray", "shoe rack", "hook rail", "woven basket", "console table", "tray shelf"],
        "textiles-rugs": ["runner rug", "throw blanket", "cushion cover set", "window panel", "bed throw", "sheer curtain", "door mat", "seat pad", "blanket ladder", "wool rug", "pillow insert", "sofa throw", "table textile set"],
        "storage-organization": ["pegboard set", "drawer insert", "storage box", "closet organizer", "wall rail", "basket set", "wire shelf", "cube shelf", "underbed bag", "label bin", "shoe box", "rolling cart", "corner shelf"],
        "decor-mirrors": ["wall mirror", "leaning mirror", "vase set", "frame trio", "scented candle", "side planter", "floating shelf", "wall clock", "table mirror", "accent tray", "ceramic bowl", "wall hook set", "picture ledge"],
    }

    seeded = list(SPECIAL_PRODUCTS)
    filler_index = 0
    for category_slug, names in base_names.items():
        existing = sum(1 for product in seeded if product["category_slug"] == category_slug)
        needed = 13 - existing
        room_slug = categories[category_slug]
        for i in range(needed):
            seeded.append(product_record(filler_index + i, category_slug, room_slug, names[i]))
        filler_index += needed

    products: list[Product] = []
    for index, raw in enumerate(seeded):
        bg, accent = category_palette(index)
        slug = slugify(raw["name"])
        image_rel = f"images/products/{raw['sku']}.svg"
        svg_card(
            STATIC_IMAGES / "products" / f"{raw['sku']}.svg",
            raw["name"],
            f"{raw['series']} · {raw['color']}",
            bg,
            accent,
        )
        products.append(
            Product(
                sku=raw["sku"],
                name=raw["name"],
                series=raw["series"],
                slug=slug,
                category_slug=raw["category_slug"],
                room_slug=raw["room_slug"],
                description=f"{raw['name']} brings {raw['room_slug'].replace('-', ' ')} storage and calm function into this local demo mirror.",
                material=raw["material"],
                color=raw["color"],
                dimensions=raw["dimensions"],
                assembly_level=raw["assembly"],
                price=raw["price"],
                list_price=raw["list_price"],
                rating=round(4.1 + ((index % 9) * 0.1), 1),
                review_count=2 + (index % 4),
                availability_bucket=["Ready for pickup", "Low stock", "Delivery in 2-5 days"][index % 3],
                delivery_note=["Parcel delivery", "Truck delivery", "Room-of-choice delivery"][index % 3],
                pickup_badge=["Pickup today", "Pickup tomorrow", "Schedule pickup"][index % 3],
                image_path=image_rel,
                gallery_json=dumps_json([image_rel]),
                features_json=dumps_json([
                    f"{raw['color']} finish",
                    raw["assembly"],
                    f"Built for the {raw['room_slug'].replace('-', ' ')}",
                ]),
                specs_json=dumps_json(raw["specs"]),
                tags_json=dumps_json(raw["tags"]),
                is_featured=raw["featured"],
                is_new=index % 8 == 0,
                is_deal=raw["deal"],
                is_bestseller=index % 10 == 0,
                compare_group=raw["category_slug"],
            )
        )
    return products


def build_support_articles() -> list[SupportArticle]:
    article_specs = [
        ("Click and collect pickup windows", "click-and-collect-pickup-windows", "Pickup", "How to choose a pickup slot and what to bring to the store."),
        ("Large item delivery for sofas and beds", "large-item-delivery", "Delivery", "What room-of-choice delivery includes for oversized furniture."),
        ("Order lookup and status notes", "order-lookup-status", "Orders", "Where to find your order number and how local demo statuses move."),
        ("Returns and exchanges in the local demo", "returns-and-exchanges", "Returns", "How returns are explained in this mirror without real transactions."),
        ("Assembly planning and service add-ons", "assembly-planning-service", "Services", "What assembly planning covers and what it does not in the demo."),
        ("Kitchen planning appointments", "kitchen-planning-appointments", "Planning", "How to book a design conversation in the mirror experience."),
        ("IKEA Family points and order rewards", "family-points-and-rewards", "Rewards", "How points accrue from synthetic orders in the local benchmark."),
        ("Mattress delivery and room-of-choice setup", "mattress-delivery-room-choice", "Delivery", "A walkthrough for bedroom deliveries and stairs notes."),
        ("Store amenities and Swedish Restaurant hours", "store-amenities-and-restaurant-hours", "Stores", "How to check store amenities, dining, and planning desks."),
        ("Pickup order readiness notifications", "pickup-readiness-notifications", "Pickup", "What the demo means when an order says pickup ready."),
        ("Protection plans for desks and chairs", "protection-plans-desks-chairs", "Protection plans", "Compare accident coverage and finish protection on work-from-home pieces."),
        ("Protection plans for sofas and beds", "protection-plans-sofas-beds", "Protection plans", "Understand coverage windows for upholstery and sleep furniture."),
        ("How to use the room planner bundles", "room-planner-bundles", "Planning", "Use curated room bundles before adding multiple products to cart."),
        ("Store pickup vs parcel delivery", "pickup-vs-parcel-delivery", "Delivery", "Choose the best fulfillment path for compact home accessories."),
        ("Truck delivery for heavy storage", "truck-delivery-heavy-storage", "Delivery", "What to expect when shelving and wardrobes need truck delivery."),
        ("Updating account preferences", "updating-account-preferences", "Account", "Change preferred store, ZIP code, and newsletter settings."),
        ("Wishlist and compare lists", "wishlist-and-compare-lists", "Account", "Keep products handy before building a room or checking out."),
        ("Bedroom storage measurement tips", "bedroom-storage-measurement-tips", "Planning", "Double-check widths and depths before choosing dressers and wardrobes."),
        ("Outdoor furniture seasonal care", "outdoor-furniture-seasonal-care", "Care", "Cleaning notes for patio seating and balcony tables."),
        ("Textile care and blackout curtains", "textile-care-and-blackout-curtains", "Care", "Laundry and hanging guidance for demo textile products."),
        ("Bathroom storage in small spaces", "bathroom-storage-small-spaces", "Planning", "Ways to fit mirror cabinets and rolling carts into tighter footprints."),
        ("Kids room safety anchors", "kids-room-safety-anchors", "Safety", "Anchor guidance for toy storage, desks, and wardrobes."),
        ("Entryway organization for narrow hallways", "entryway-organization-narrow-hallways", "Planning", "Choose shoe cabinets and hooks for tight drop zones."),
        ("Lighting bundles for open-plan rooms", "lighting-bundles-open-plan-rooms", "Planning", "Mix floor, pendant, and task lighting without overwhelming a room."),
    ]
    articles = []
    for title, slug, category, summary in article_specs:
        articles.append(
            SupportArticle(
                title=title,
                slug=slug,
                category=category,
                summary=summary,
                body=(
                    f"{summary}\n\n"
                    "This is a local benchmark mirror using deterministic demo data. "
                    "No real orders, payments, delivery bookings, or external APIs are involved."
                ),
                related_topics_json=dumps_json(["delivery", "pickup", "planning", "support"]),
            )
        )
    return articles


def build_deals(products: list[Product]) -> list[Deal]:
    chosen = [product for product in products if product.is_deal][:18]
    deals = []
    for idx, product in enumerate(chosen):
        deals.append(
            Deal(
                title=f"{product.series} spotlight",
                slug=f"deal-{product.sku.lower()}",
                category_slug=product.category_slug,
                badge=["Weekend offer", "Family pick", "Room refresh"][idx % 3],
                summary=f"Save on {product.name} while keeping the room plan under budget.",
                discount_text=f"Save {int(round(product.list_price - product.price))} dollars",
                product_sku=product.sku,
            )
        )
    return deals


def build_room_bundles(products: list[Product]) -> list[RoomBundle]:
    bundles: list[RoomBundle] = []
    room_groups = {}
    for product in products:
        room_groups.setdefault(product.room_slug, []).append(product)
    for room_slug, items in room_groups.items():
        selected = items[:3]
        bundles.append(
            RoomBundle(
                name=f"{ROOM_LABELS[room_slug]} starter plan",
                slug=f"{room_slug}-starter-plan",
                room_slug=room_slug,
                summary=f"Three coordinated picks for a quick {ROOM_LABELS[room_slug].lower()} refresh.",
                total_price=round(sum(item.price for item in selected), 2),
                item_skus_json=dumps_json([item.sku for item in selected]),
                hero_note="Curated bundle built from deterministic demo inventory.",
            )
        )
    return bundles


def seed_database(force: bool = False) -> None:
    if Category.query.count() > 0 and not force:
        return

    if force:
        db.drop_all()
        db.create_all()

    categories = build_categories()
    stores = build_stores()
    products = build_products()
    articles = build_support_articles()
    deals = build_deals(products)
    bundles = build_room_bundles(products)

    db.session.add_all(categories)
    db.session.add_all(stores)
    db.session.add_all(products)
    db.session.add_all(articles)
    db.session.add_all(deals)
    db.session.add_all(bundles)

    db.session.add_all(
        [
            DeliveryOption(slug="parcel", name="Parcel delivery", fee=19.0, window_label="Arrives in 2-5 days", description="Compact items shipped to your door.", carbon_note="Lower-impact route"),
            DeliveryOption(slug="truck", name="Truck delivery", fee=79.0, window_label="Choose a 4-hour window", description="Large furniture delivery with threshold drop-off.", carbon_note="Best for wardrobes and sofas"),
            DeliveryOption(slug="room-choice", name="Room-of-choice delivery", fee=109.0, window_label="Choose a 2-hour window", description="Large items delivered into the room you select.", carbon_note="Includes upstairs carry in this demo"),
        ]
    )

    db.session.flush()

    for store_index, store in enumerate(stores):
        for slot_index in range(3):
            db.session.add(
                PickupSlot(
                    store_id=store.id,
                    slot_date=f"2026-06-{8 + slot_index:02d}",
                    time_window=["10:00-12:00", "1:00-3:00", "5:00-7:00"][slot_index],
                    remaining_capacity=12 - ((store_index + slot_index) % 5),
                )
            )

    for product_index, product in enumerate(products):
        review_total = 2 + (product_index % 4)
        for review_index in range(review_total):
            db.session.add(
                Review(
                    product_id=product.id,
                    author_name=f"Demo shopper {product_index + review_index + 1}",
                    headline=[
                        "Looks polished in person",
                        "Easy to style in a small room",
                        "Great value for the size",
                        "Helpful storage details",
                    ][review_index % 4],
                    body=(
                        f"{product.name} works well in this synthetic benchmark home. "
                        f"I picked the {product.color.lower()} option and liked the {product.material.lower()} finish."
                    ),
                    rating=4 + (review_index % 2),
                    helpful_count=4 + review_index * 3,
                    created_on=f"2026-05-{10 + review_index:02d}",
                )
            )
        for plan_years, plan_price in ((3, round(product.price * 0.08, 2)), (5, round(product.price * 0.13, 2))):
            db.session.add(
                ProtectionPlan(
                    product_id=product.id,
                    name=f"{plan_years}-year home protection",
                    years=plan_years,
                    price=plan_price,
                    description="Covers finish issues, hardware replacements, and accidental stains in this demo.",
                    benefits_json=dumps_json([
                        "Finish coverage",
                        "Replacement hardware",
                        "Priority support script",
                    ]),
                )
            )
        for store_index, store in enumerate(stores):
            quantity = 3 + ((product_index + store_index) % 14)
            db.session.add(
                StoreInventory(
                    store_id=store.id,
                    product_id=product.id,
                    quantity=quantity,
                    aisle=f"{chr(65 + (store_index % 5))}-{10 + (product_index % 9)}",
                    pickup_available=quantity > 2,
                    delivery_available=(product_index + store_index) % 5 != 0,
                )
            )

    db.session.commit()


def seed_benchmark_users(force: bool = False) -> None:
    if User.query.filter_by(email="alice.j@test.com").first() and not force:
        return

    if force:
        CompareItem.query.delete()
        WishlistItem.query.delete()
        CartItem.query.delete()
        RewardActivity.query.delete()
        PaymentMock.query.delete()
        OrderItem.query.delete()
        Order.query.delete()
        SupportTicket.query.delete()
        User.query.delete()
        db.session.commit()

    profiles = [
        ("alice.j@test.com", "Alice", "Jones", "Brooklyn", "NY", "11215", "brooklyn-ny", 940),
        ("bob.c@test.com", "Bob", "Chen", "Austin", "TX", "78758", "round-rock-tx", 720),
        ("carol.d@test.com", "Carol", "Diaz", "Atlanta", "GA", "30318", "atlanta-ga", 860),
        ("david.k@test.com", "David", "Kim", "Tempe", "AZ", "85281", "tempe-az", 680),
    ]
    users = []
    for email, first_name, last_name, city, state, zip_code, preferred_store, points in profiles:
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone="555-0100",
            city=city,
            state=state,
            zip_code=zip_code,
            preferred_store_slug=preferred_store,
            rewards_points=points,
        )
        user.set_password("TestPass123!")
        users.append(user)
    db.session.add_all(users)
    db.session.flush()

    products = {product.sku: product for product in Product.query.order_by(Product.sku.asc()).all()}
    stores = {store.slug: store for store in Store.query.order_by(Store.slug.asc()).all()}

    wishlist_sets = {
        "alice.j@test.com": ["IK-10001", "IK-10003", "IK-10005", "IK-10017"],
        "bob.c@test.com": ["IK-10007", "IK-10008", "IK-10021", "IK-10022"],
        "carol.d@test.com": ["IK-10009", "IK-10010", "IK-10019", "IK-10024"],
        "david.k@test.com": ["IK-10013", "IK-10015", "IK-10018", "IK-10023"],
    }
    compare_sets = {
        "alice.j@test.com": ["IK-10001", "IK-10002", "IK-10015"],
        "bob.c@test.com": ["IK-10007", "IK-10008", "IK-10021"],
        "carol.d@test.com": ["IK-10005", "IK-10006", "IK-10019"],
        "david.k@test.com": ["IK-10013", "IK-10014", "IK-10024"],
    }
    cart_sets = {
        "alice.j@test.com": [("IK-10002", 1), ("IK-10017", 1)],
        "bob.c@test.com": [("IK-10007", 1), ("IK-10022", 2)],
        "carol.d@test.com": [("IK-10005", 1), ("IK-10020", 2)],
        "david.k@test.com": [("IK-10013", 1), ("IK-10015", 1)],
    }

    for user in users:
        for sku in wishlist_sets[user.email]:
            db.session.add(WishlistItem(user_id=user.id, product_id=products[sku].id, created_on="2026-05-30"))
        for sku in compare_sets[user.email]:
            db.session.add(CompareItem(user_id=user.id, product_id=products[sku].id, created_on="2026-05-28"))
        for sku, quantity in cart_sets[user.email]:
            db.session.add(CartItem(user_id=user.id, product_id=products[sku].id, quantity=quantity))

        for idx in range(5):
            db.session.add(
                RewardActivity(
                    user_id=user.id,
                    label=[
                        "Spring room refresh order",
                        "Wishlist inspiration bonus",
                        "Pickup ready bonus",
                        "Local planning appointment",
                        "Bedroom storage order",
                    ][idx],
                    points_delta=[120, 35, 40, 55, 160][idx],
                    activity_type=["purchase", "bonus", "bonus", "service", "purchase"][idx],
                    occurred_on=f"2026-05-{20 + idx:02d}",
                )
            )

    statuses = [
        "Preparing order",
        "Ready for pickup",
        "Out for delivery",
        "Delivered",
        "Delivered",
        "Awaiting customer pickup",
    ]
    seeded_skus = list(products.keys())
    for order_index in range(60):
        user = users[order_index % 4]
        store = stores[user.preferred_store_slug]
        order_number = f"IK-24{order_index + 1:04d}"
        fulfillment = "pickup" if order_index % 3 == 0 else "delivery"
        order = Order(
            order_number=order_number,
            user_id=user.id,
            store_id=store.id,
            fulfillment_method=fulfillment,
            status=statuses[order_index % len(statuses)],
            subtotal=0.0,
            shipping_fee=0.0 if fulfillment == "pickup" else [19.0, 79.0, 109.0][order_index % 3],
            tax=0.0,
            total=0.0,
            placed_on=f"2026-04-{1 + (order_index % 28):02d}",
            delivery_window="2026-04-18 · 1:00 PM - 5:00 PM" if fulfillment == "delivery" else "",
            pickup_window="2026-04-18 · 10:00 AM - 12:00 PM" if fulfillment == "pickup" else "",
            contact_name=user.full_name,
            payment_summary=f"Local demo card •••• {4242 + (order_index % 4)}",
        )
        db.session.add(order)
        db.session.flush()
        selected = [
            products[seeded_skus[(order_index * 3) % len(seeded_skus)]],
            products[seeded_skus[(order_index * 3 + 7) % len(seeded_skus)]],
        ]
        subtotal = 0.0
        for item_index, product in enumerate(selected):
            quantity = 1 if item_index == 0 else 1 + (order_index % 2)
            subtotal += product.price * quantity
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.price,
                )
            )
        order.subtotal = round(subtotal, 2)
        order.tax = round(subtotal * 0.085, 2)
        order.total = round(order.subtotal + order.shipping_fee + order.tax, 2)
        db.session.add(
            PaymentMock(
                order_id=order.id,
                method_label=["IKEA Family Visa", "Demo Mastercard", "Demo Klarna"][order_index % 3],
                last_four=str(4242 + (order_index % 4)),
                billing_name=user.full_name,
                status="Settled in local demo",
            )
        )

    for idx, user in enumerate(users):
        for ticket_index in range(2):
            db.session.add(
                SupportTicket(
                    ticket_number=f"SUP-{idx + 1}{ticket_index + 1:03d}",
                    user_id=user.id,
                    subject=[
                        "Pickup readiness clarification",
                        "Assembly planning follow-up",
                    ][ticket_index],
                    status=["Waiting on customer", "Resolved"][ticket_index],
                    article_slug=["pickup-readiness-notifications", "assembly-planning-service"][ticket_index],
                    opened_on=f"2026-05-{12 + ticket_index:02d}",
                    note="Demo support notes only; no live customer service is connected.",
                )
            )

    db.session.commit()


def build_seed_database() -> None:
    STATIC_IMAGES.mkdir(parents=True, exist_ok=True)
    INSTANCE_SEED_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_database(force=True)
        seed_benchmark_users(force=True)
    shutil.copyfile(DB_PATH, INSTANCE_SEED_DIR / "ikea.db")


if __name__ == "__main__":
    build_seed_database()
    print("Seed database and local SVG assets generated for IKEA.")
