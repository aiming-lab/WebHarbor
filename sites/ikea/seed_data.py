"""Deterministic seed data for the IKEA demo."""
from __future__ import annotations

import json
import os
import random
import shutil
from html import escape
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

from app import (
    BASE_DIR,
    DB_PATH,
    ROOM_LABELS,
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
    Review,
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

RNG = random.Random(20260604)
STATIC_IMAGES = BASE_DIR / "static" / "images"
INSTANCE_SEED_DIR = BASE_DIR / "instance_seed"
CATALOG_PATH = BASE_DIR / "catalog_source.json"

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

DEMO_PASSWORD_HASHES = {
    "alice.j@test.com": "scrypt:32768:8:1$xcmAKpVh63o52xg5$4e2247333415e6456fcc2a9fb8a1992e60c6e480265a8329ab4e70ebd12a7f3f6a2bc8a2b9e4ebc6b5e2f643907ae386bc45f92944dd2781e65e710ce417be31",
    "bob.c@test.com": "scrypt:32768:8:1$TcYuBxSULboyQlXd$a272950532742665702c9213240397d98813f3dc168eef9b111056b87b1a5b7d780e5db68d6c195213d361a6139bb6106da9f55203110bb391e005bc4e65b9e2",
    "carol.d@test.com": "scrypt:32768:8:1$wjZQydR4MNwZtlle$615e55b19282a00da9edd521aaaf3e8e958a3499d6f8c015233932645ff850818d10a4d678780dcd94960296139415c2e361e079894bcfd448e2c767389355a7",
    "david.k@test.com": "scrypt:32768:8:1$900NA9uGsdnrM2sF$de666f57af7a35750107e5240efef515f699c54a5ffa127cfa6d63beb125b6c5ad5bc7a1b021ea38c4bef8560b88e7cfa0ea50905427cec8bf38ef58f20c3323",
}

REVIEW_AUTHORS = [
    "Alex R.", "Brianna M.", "Chris T.", "Dana L.", "Eli S.", "Fatima K.",
    "Grace P.", "Henry W.", "Isabel C.", "Jordan N.", "Kai B.", "Leah D.",
]

REVIEW_HEADLINES = [
    "Looks just like the photos", "A practical fit for our space", "Solid after daily use", "Thoughtful details", "Easy to plan around", "Good value for the size", "Clean design and finish", "Works well with the room", "Measurements were accurate", "Simple to care for", "Comfortable and sturdy", "Would buy from this series again",
]

REVIEW_BODIES = [
    "The photos and measurements were accurate, so it was easy to plan the space before delivery.",
    "The finish looks consistent in daylight and the construction feels stable during everyday use.",
    "Packaging protected the corners and surfaces well. Everything arrived clean and ready to set up.",
    "After several weeks, it has been easy to care for and still looks new.",
    "The proportions work well with the other pieces in our room without making the space feel crowded.",
    "The materials feel appropriate for the price, and the small functional details are genuinely useful.",
]

SUPPORT_BODY_PARAGRAPHS = {
    "click-and-collect-pickup-windows": [
        "Choose a store during checkout to see its current collection windows. The available times shown for one location may differ from another because each store manages its own capacity.",
        "Wait until the readiness message arrives before traveling to the store. Bring the order number and photo identification, then follow the signs for Click & collect at the selected location.",
    ],
    "large-item-delivery": [
        "Sofas, beds, wardrobes, and other bulky furniture can use Room-of-choice delivery. The delivery team carries packaged items inside and places them in the room selected during checkout, including an upstairs room when the route is safe and accessible.",
        "Measure doors, hallways, elevators, and stair turns before the appointment. Clear the route, secure pets, and make sure an adult is available throughout the delivery window. Assembly and packaging removal are separate services unless they are listed on the order.",
    ],
    "order-lookup-status": [
        "Enter the order number and the email address used at checkout. Both values must match before status or order details are shown.",
        "Preparing order means the items are being gathered. Ready for pickup means collection instructions have been sent. Out for delivery means the order has left the local facility, while Delivered closes the shipment workflow.",
    ],
    "returns-and-exchanges": [
        "Start with the order detail page so the item, purchase date, and payment method are available. Store returns should include the product, receipt or order number, and all parts that came in the package.",
        "Opened, assembled, or damaged products may require an inspection before a refund method is selected. This local store experience records no real return or refund transaction.",
    ],
    "assembly-planning-service": [
        "Assembly planning helps identify which items need installation, how much clear floor space is required, and whether wall anchoring or utility access is part of the work.",
        "A planning appointment does not automatically add assembly to an order. Review the service scope and price separately before checkout, and keep the product area clear for the scheduled visit.",
    ],
    "kitchen-planning-appointments": [
        "Before a kitchen planning appointment, measure wall lengths, ceiling height, doors, windows, and the location of plumbing, electrical outlets, and ventilation. Photos of the existing room are also useful.",
        "The planner can review cabinet layouts, worktop options, storage needs, and appliance clearances. Final installation measurements should be confirmed before products are ordered.",
    ],
    "family-points-and-rewards": [
        "Eligible purchases and selected activities add points after they appear in account history. The rewards page lists each activity label, date, type, and point change in newest-first order.",
        "Canceled or returned purchases can result in an adjustment. Points in this local experience are illustrative and cannot be redeemed outside the mirror.",
    ],
    "mattress-delivery-room-choice": [
        "Room-of-choice service can carry a packaged mattress or bed frame to the bedroom selected at checkout. The route must have enough clearance for doors, landings, stairs, and elevator turns.",
        "Protect floors, remove fragile objects from the path, and tell the delivery team about access restrictions in advance. Mattress setup, old-mattress removal, and frame assembly are included only when specifically listed.",
    ],
    "store-amenities-and-restaurant-hours": [
        "Open a store detail page to see amenities available at that location, such as the Swedish Restaurant, Click & collect, planning areas, or family facilities.",
        "Store and restaurant hours can differ, especially around holidays. Confirm the listed location and opening time before starting a visit.",
    ],
    "pickup-readiness-notifications": [
        "A readiness notification is sent after store staff have gathered the order and assigned it to the collection area. An order confirmation by itself does not mean the items are ready to collect.",
        "Use the order number and the email address from checkout when checking status. After the ready message arrives, go to the selected store during the stated window and follow its Click & collect instructions.",
    ],
    "protection-plans-desks-chairs": [
        "Review the coverage term, covered incidents, exclusions, and service process before adding a plan. A shorter plan focuses on essential hardware and finish issues, while extended coverage can include additional accidental-damage benefits.",
        "Keep the order record and photographs of the item. Normal wear, intentional damage, commercial use, and problems present before coverage begins are not included.",
    ],
    "protection-plans-sofas-beds": [
        "Furniture protection for sofas and beds can cover specified frame, hardware, upholstery, or stain incidents during the selected term. The exact benefits shown on the product page determine what is included.",
        "Manufacturer warranty coverage and a protection plan are separate. Review exclusions for normal wear, pet damage, moving damage, and unauthorized repairs before choosing a term.",
    ],
    "room-planner-bundles": [
        "Each room planner bundle lists the three products included and the combined item price. Review the product names and prices before adding the bundle because the action adds every listed item to the cart.",
        "After adding a bundle, open the cart to adjust quantities or remove individual products. Availability and delivery options are evaluated per item during checkout.",
    ],
    "pickup-vs-parcel-delivery": [
        "Store pickup is useful when a nearby location has stock and a suitable collection window. Parcel delivery sends eligible compact items to the address entered during checkout.",
        "Large or heavy products may require truck delivery instead. Compare the fee, timing, item eligibility, and travel required before selecting a fulfillment method.",
    ],
    "truck-delivery-heavy-storage": [
        "Shelving, wardrobes, and other heavy storage pieces may be assigned to truck delivery because their packages are too large for parcel service. Checkout shows the available window and fee.",
        "Check package dimensions, clear the delivery route, and plan for safe wall anchoring after assembly. Threshold delivery does not include carrying products to a specific room unless that service is selected.",
    ],
    "updating-account-preferences": [
        "The profile page lets a signed-in member update their name, phone number, city, state, ZIP code, preferred store, and newsletter choice.",
        "Saving a preferred store changes which location is suggested during shopping and pickup. It does not modify an existing order or move inventory between stores.",
    ],
    "wishlist-and-compare-lists": [
        "Use the wishlist for products you want to keep for later. A saved item remains on the wishlist when it is added to the cart unless you remove it separately.",
        "Compare holds up to four products and presents their price, availability, rating, and available specification rows side by side. Remove one product before adding another when the list is full.",
    ],
    "bedroom-storage-measurement-tips": [
        "Measure the wall width, ceiling height, baseboards, outlets, door swing, and the space needed to open drawers or wardrobe doors. Record the narrowest point on the delivery route as well.",
        "Compare those measurements with the product dimensions and anchoring instructions. Leave practical clearance for cleaning, ventilation, and daily use.",
    ],
    "outdoor-furniture-seasonal-care": [
        "Clean frames with a mild soapy solution and let every surface dry before covering or storing the furniture. Remove cushions during prolonged rain and follow their individual care labels.",
        "Tighten hardware at the start and end of the season. Store pieces in a dry, ventilated space when possible, and avoid trapping moisture under a cover.",
    ],
    "textile-care-and-blackout-curtains": [
        "Check the sewn-in care label before washing curtains or cushion covers. Remove hooks and other hardware, use the listed temperature, and avoid bleach or tumble drying when the instructions prohibit them.",
        "Measure from the rail to the desired hem before hanging curtains. Heading tape can be used with rods, hooks, or tracks depending on the product instructions.",
    ],
    "bathroom-storage-small-spaces": [
        "Use wall height and shallow storage to keep the floor area open. Measure around doors, plumbing, radiators, and electrical zones before selecting a cabinet or cart.",
        "Choose moisture-resistant materials and leave room for ventilation. Wall-mounted products must use fasteners suitable for the wall construction.",
    ],
    "kids-room-safety-anchors": [
        "Tall or climbable storage must be secured to the wall with appropriate fasteners. Place heavier items lower, keep cords out of reach, and do not position climbable furniture next to a window.",
        "Wall materials require different screws and plugs. If the supplied restraint is not suitable, obtain compatible hardware before using the product.",
    ],
    "entryway-organization-narrow-hallways": [
        "Measure walking clearance with cabinet doors and drawers open. Shallow shoe storage, wall hooks, and a compact bench can organize daily items without blocking the route.",
        "Anchor tall cabinets and keep frequently used items within easy reach. Leave exits, electrical panels, and heating equipment unobstructed.",
    ],
    "lighting-bundles-open-plan-rooms": [
        "Use ambient light for the whole room, task light over work areas, and focused accent light for shelves or artwork. Separate controls make the open space easier to adapt through the day.",
        "Check bulb base, maximum wattage, dimmer compatibility, cord routing, and installation requirements for every fixture before combining products.",
    ],
}

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
<text x="88" y="520" fill="#111827" font-family="Arial, sans-serif" font-size="44" font-weight="700">{escape(title)}</text>
<text x="88" y="574" fill="#4b5563" font-family="Arial, sans-serif" font-size="28">{escape(subtitle)}</text>
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


def build_products() -> list[Product]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    seeded = catalog["products"]
    if len(seeded) != 156:
        raise ValueError(f"IKEA catalog must contain 156 products, got {len(seeded)}")

    products: list[Product] = []
    for index, raw in enumerate(seeded):
        sku = raw["local_sku"]
        material = raw["materials"][0] if raw["materials"] else ""
        features = raw["good_to_know"][:3] or raw["care_instructions"][:3]
        specs = {"IKEA product ID": raw["source_product_id"]}
        if material:
            specs["Material"] = material
        if raw["dimensions"]:
            specs["Size"] = raw["dimensions"]
        if raw["care_instructions"]:
            specs["Care"] = raw["care_instructions"][0]
        is_deal = index % 7 == 0
        price = raw["price"]
        products.append(
            Product(
                sku=sku,
                name=raw["name"],
                series=raw["series"],
                slug=f"{slugify(raw['name'])}-{sku.lower()}",
                category_slug=raw["category_slug"],
                room_slug=raw["room_slug"],
                description=raw["description"],
                material=material,
                color=raw["color"],
                dimensions=raw["dimensions"],
                assembly_level="",
                price=price,
                list_price=round(price * 1.12, 2) if is_deal else price,
                rating=round(4.1 + ((index % 9) * 0.1), 1),
                review_count=2 + (index % 4),
                availability_bucket=["Ready for pickup", "Low stock", "Delivery in 2-5 days"][index % 3],
                delivery_note=["Parcel delivery", "Truck delivery", "Room-of-choice delivery"][index % 3],
                pickup_badge=["Pickup today", "Pickup tomorrow", "Schedule pickup"][index % 3],
                image_path=raw["image_path"],
                gallery_json=dumps_json([raw["image_path"]]),
                features_json=dumps_json(features),
                specs_json=dumps_json(specs),
                tags_json=dumps_json(raw["source_category_tree"]),
                is_featured=index % 9 == 0,
                is_new=index % 8 == 0,
                is_deal=is_deal,
                is_bestseller=index % 10 == 0,
                compare_group=raw["category_slug"],
            )
        )
    return products


def build_support_articles() -> list[SupportArticle]:
    article_specs = [
        ("Click and collect pickup windows", "click-and-collect-pickup-windows", "Pickup", "How to choose a pickup slot and what to bring to the store."),
        ("Large item delivery for sofas and beds", "large-item-delivery", "Delivery", "What to expect when ordering delivery for sofas, beds, and other bulky furniture."),
        ("Order lookup and status notes", "order-lookup-status", "Orders", "Where to find your order number and how local demo statuses move."),
        ("Returns and exchanges in the local demo", "returns-and-exchanges", "Returns", "How returns are explained in this mirror without real transactions."),
        ("Assembly planning and service add-ons", "assembly-planning-service", "Services", "What assembly planning covers and what it does not in the demo."),
        ("Kitchen planning appointments", "kitchen-planning-appointments", "Planning", "How to book a design conversation in the mirror experience."),
        ("IKEA Family points and order rewards", "family-points-and-rewards", "Rewards", "How points accrue from synthetic orders in the local benchmark."),
        ("Mattress delivery and room-of-choice setup", "mattress-delivery-room-choice", "Delivery", "A walkthrough for bedroom deliveries and stairs notes."),
        ("Store amenities and Swedish Restaurant hours", "store-amenities-and-restaurant-hours", "Stores", "How to check store amenities, dining, and planning desks."),
        ("When your collection order is ready", "pickup-readiness-notifications", "Pickup", "How collection messages and store instructions work after an order is prepared."),
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
                body="\n\n".join(SUPPORT_BODY_PARAGRAPHS[slug]),
                related_topics_json=dumps_json([category.lower(), "shopping help", "customer service"]),
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
                discount_text=f"Save {round(product.list_price - product.price)} dollars",
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
            review_variant = product_index * 3 + review_index
            db.session.add(
                Review(
                    product_id=product.id,
                    author_name=REVIEW_AUTHORS[review_variant % len(REVIEW_AUTHORS)],
                    headline=REVIEW_HEADLINES[review_variant % len(REVIEW_HEADLINES)],
                    body=REVIEW_BODIES[review_variant % len(REVIEW_BODIES)],
                    rating=4 + (review_index % 2),
                    helpful_count=4 + review_index * 3,
                    created_on=f"2026-08-{10 + review_index:02d}",
                )
            )
        plan_options = (
            (
                3,
                round(product.price * 0.08, 2),
                "Essential coverage for eligible finish defects and functional hardware after the product warranty.",
                ["Eligible finish repair", "Functional hardware replacement", "Parts and labor for approved claims"],
            ),
            (
                5,
                round(product.price * 0.13, 2),
                "Extended coverage that adds selected accidental stains and damage for two additional years.",
                ["All 3-year plan benefits", "Accidental stain and tear coverage", "One approved replacement if repair is not practical"],
            ),
        )
        for plan_years, plan_price, plan_description, plan_benefits in plan_options:
            db.session.add(
                ProtectionPlan(
                    product_id=product.id,
                    name=f"{plan_years}-year home protection",
                    years=plan_years,
                    price=plan_price,
                    description=plan_description,
                    benefits_json=dumps_json(plan_benefits),
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
            password_hash=DEMO_PASSWORD_HASHES[email],
            first_name=first_name,
            last_name=last_name,
            phone="555-0100",
            city=city,
            state=state,
            zip_code=zip_code,
            preferred_store_slug=preferred_store,
            rewards_points=points,
        )
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
    print("Seed database generated from the deterministic IKEA source catalog.")
