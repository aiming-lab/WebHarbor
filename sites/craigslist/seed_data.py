"""Deterministic seed data for the Craigslist mirror."""
from datetime import datetime, timedelta
import hashlib
import json
import os
import re


FIXED_NOW = datetime(2026, 5, 12, 9, 30, 0)


CATEGORY_GROUPS = [
    {
        "slug": "for_sale",
        "name": "for sale",
        "columns": [
            ("furniture", "furniture", "fua"),
            ("electronics", "electronics", "ela"),
            ("bikes", "bikes", "bia"),
            ("cars_trucks", "cars+trucks", "cta"),
            ("appliances", "appliances", "ppa"),
            ("free", "free stuff", "zip"),
            ("musical", "musical instruments", "msa"),
            ("sporting", "sporting goods", "sga"),
            ("tools", "tools", "tla"),
        ],
    },
    {
        "slug": "housing",
        "name": "housing",
        "columns": [
            ("apartments", "apts / housing", "apa"),
            ("rooms_shares", "rooms / shared", "roo"),
            ("sublets", "sublets / temporary", "sub"),
            ("parking", "parking / storage", "prk"),
            ("office_commercial", "office / commercial", "off"),
        ],
    },
    {
        "slug": "jobs",
        "name": "jobs",
        "columns": [
            ("software", "software / qa", "sof"),
            ("customer_service", "customer service", "csr"),
            ("food_bev_hosp", "food / bev / hosp", "fbh"),
            ("general_labor", "general labor", "lab"),
            ("healthcare", "healthcare", "hea"),
            ("education", "education", "edu"),
            ("sales", "sales", "sls"),
            ("skilled_trade", "skilled trades", "trd"),
        ],
    },
    {
        "slug": "services",
        "name": "services",
        "columns": [
            ("automotive_services", "automotive", "aos"),
            ("computer_services", "computer", "cps"),
            ("creative_services", "creative", "crs"),
            ("household_services", "household", "hss"),
            ("labor_move", "labor / move", "lbs"),
            ("lessons", "lessons", "lss"),
        ],
    },
    {
        "slug": "community",
        "name": "community",
        "columns": [
            ("events", "events", "eve"),
            ("volunteers", "volunteers", "vol"),
            ("artists", "artists", "ats"),
            ("classes", "classes", "cls"),
            ("groups", "groups", "grp"),
            ("lost_found", "lost+found", "laf"),
        ],
    },
]


REGIONS = [
    "san francisco",
    "east bay",
    "south bay",
    "peninsula",
    "north bay",
    "santa cruz",
]


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "listing"


def deterministic_password(email, password="TestPass123!"):
    payload = f"{email}:{password}:webharbor-craigslist".encode("utf-8")
    return "sha256$" + hashlib.sha256(payload).hexdigest()


def image_pool(base_dir):
    img_dir = os.path.join(base_dir, "static", "images")
    pools = {
        "furniture": [],
        "cars_trucks": [],
        "apartments": [],
        "jobs": [],
    }
    if not os.path.isdir(img_dir):
        return pools
    for filename in sorted(os.listdir(img_dir)):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        rel = f"images/{filename}"
        for prefix in pools:
            if filename.startswith(prefix + "_"):
                pools[prefix].append(rel)
                break
    return pools


def pick_image(pools, category_slug, idx):
    if category_slug in pools and pools[category_slug]:
        values = pools[category_slug]
        return values[idx % len(values)]
    if category_slug in {"software", "customer_service", "food_bev_hosp",
                         "general_labor", "healthcare", "education",
                         "sales", "skilled_trade"} and pools["jobs"]:
        return pools["jobs"][idx % len(pools["jobs"])]
    if category_slug in {"rooms_shares", "sublets"} and pools["apartments"]:
        return pools["apartments"][idx % len(pools["apartments"])]
    return ""


def image_gallery(pools, category_slug, idx, primary):
    if not primary:
        return []
    key = category_slug
    if key not in pools or not pools[key]:
        if category_slug in {"software", "customer_service", "food_bev_hosp",
                             "general_labor", "healthcare", "education",
                             "sales", "skilled_trade"}:
            key = "jobs"
        elif category_slug in {"rooms_shares", "sublets"}:
            key = "apartments"
    values = list(pools.get(key, []))
    if not values:
        return [primary]
    ordered = [primary]
    for offset in range(1, min(5, len(values))):
        candidate = values[(idx + offset) % len(values)]
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


AREA_MAP_BASES = {
    "san francisco": (37.7749, -122.4194, 48, 43),
    "east bay": (37.8044, -122.2712, 63, 45),
    "south bay": (37.3382, -121.8863, 70, 72),
    "peninsula": (37.5630, -122.3255, 50, 62),
    "north bay": (38.1074, -122.5697, 36, 24),
    "santa cruz": (36.9741, -122.0308, 45, 86),
}


def map_details(area, neighborhood, idx):
    lat, lng, x, y = AREA_MAP_BASES.get(area, AREA_MAP_BASES["san francisco"])
    digest = int(hashlib.md5(f"{area}:{neighborhood}:{idx}".encode("utf-8")).hexdigest()[:8], 16)
    dx = (digest % 1700) / 100 - 8.5
    dy = ((digest // 1700) % 1500) / 100 - 7.5
    return {
        "map_lat": round(lat + dy * 0.008, 5),
        "map_lng": round(lng + dx * 0.01, 5),
        "map_x": round(max(8, min(92, x + dx)), 1),
        "map_y": round(max(10, min(90, y + dy)), 1),
    }


def finalize_record(row, pools, idx):
    image = row.get("image", "")
    details = dict(row.get("details", {}))
    gallery = image_gallery(pools, row["category_slug"], idx, image)
    if gallery:
        details["images"] = gallery
    details.update(map_details(row.get("area", REGIONS[idx % len(REGIONS)]), row.get("neighborhood", "san francisco"), idx))
    row["details"] = details
    return row


SPECIAL_LISTINGS = [
    {
        "category_slug": "furniture",
        "title": "Ergonomic task chair",
        "area": "east bay",
        "neighborhood": "berkeley",
        "price": 85,
        "condition": "excellent",
        "description": "Black mesh home office chair from a smoke-free workspace. Detail table lists the adjustment options and pickup notes.",
        "details": {"material": "mesh", "color": "black", "arms": "adjustable", "seat_height": "17-21 in", "delivery": "pickup only"},
    },
    {
        "category_slug": "furniture",
        "title": "Black office chair",
        "area": "east bay",
        "neighborhood": "oakland",
        "price": 65,
        "condition": "good",
        "description": "Simple rolling office chair with a firm seat. Works best for a guest desk or short work sessions.",
        "details": {"material": "fabric", "color": "black", "arms": "fixed", "delivery": "pickup only"},
    },
    {
        "category_slug": "furniture",
        "title": "Dining chair set",
        "area": "east bay",
        "neighborhood": "alameda",
        "price": 90,
        "condition": "fair",
        "description": "Four matching dining chairs. Seats are sturdy, but two cushions have light wear.",
        "details": {"material": "wood", "color": "brown", "quantity": "4", "delivery": "buyer pickup"},
    },
    {
        "category_slug": "furniture",
        "title": "Desk chair for small office",
        "area": "east bay",
        "neighborhood": "emeryville",
        "price": 55,
        "condition": "good",
        "description": "Compact desk chair with wheels. Fits under a narrow writing desk.",
        "details": {"material": "vinyl", "color": "gray", "arms": "none", "delivery": "pickup only"},
    },
    {
        "category_slug": "furniture",
        "title": "Pair of folding chairs",
        "area": "east bay",
        "neighborhood": "berkeley",
        "price": 25,
        "condition": "good",
        "description": "Two folding chairs for extra seating. Lightweight and easy to store.",
        "details": {"material": "metal", "color": "white", "quantity": "2", "delivery": "porch pickup"},
    },
    {
        "category_slug": "furniture",
        "title": "Vintage wood chair",
        "area": "east bay",
        "neighborhood": "oakland",
        "price": 75,
        "condition": "fair",
        "description": "Vintage accent chair with carved back. Needs new felt pads on the legs.",
        "details": {"material": "wood", "color": "oak", "style": "accent", "delivery": "pickup only"},
    },
    {
        "category_slug": "furniture",
        "title": "Walnut writing desk with two drawers",
        "area": "san francisco",
        "neighborhood": "mission district",
        "price": 140,
        "condition": "good",
        "description": "Compact writing desk that fits a small apartment. Some edge wear on the back left corner.",
        "details": {"width": "42 in", "depth": "22 in", "material": "walnut veneer", "delivery": "buyer pickup"},
    },
    {
        "category_slug": "furniture",
        "title": "Standing desk frame, white",
        "area": "peninsula",
        "neighborhood": "palo alto",
        "price": 210,
        "condition": "like new",
        "description": "Electric standing desk frame, dual motor, controller works. Desktop not included.",
        "details": {"height_range": "25-50 in", "load_rating": "220 lb", "color": "white"},
    },
    {
        "category_slug": "electronics",
        "title": "Dell 27 inch USB-C monitor",
        "area": "south bay",
        "neighborhood": "sunnyvale",
        "price": 165,
        "condition": "excellent",
        "description": "Desk display with original power cable. Detail table lists the display specs.",
        "details": {"size": "27 in", "resolution": "2560x1440", "ports": "USB-C HDMI DP"},
    },
    {
        "category_slug": "electronics",
        "title": "Sony noise cancelling headphones",
        "area": "san francisco",
        "neighborhood": "nob hill",
        "price": 120,
        "condition": "good",
        "description": "Over-ear wireless headphones with case and USB cable. Ear pads replaced last month.",
        "details": {"battery": "24 hours", "color": "silver", "included": "case cable"},
    },
    {
        "category_slug": "bikes",
        "title": "Marin commuter bike",
        "area": "east bay",
        "neighborhood": "oakland lake merritt",
        "price": 460,
        "condition": "good",
        "description": "Medium frame city bike with fenders, rear rack, and recent tune-up. Braking details are in the table below.",
        "details": {"frame": "medium", "brakes": "hydraulic disc", "gears": "1x10", "wheel_size": "700c"},
    },
    {
        "category_slug": "bikes",
        "title": "Trek hybrid bike, large frame",
        "area": "north bay",
        "neighborhood": "san rafael",
        "price": 520,
        "condition": "excellent",
        "description": "Large hybrid bike with flat bars, new chain, and puncture-resistant tires.",
        "details": {"frame": "large", "brakes": "rim", "gears": "3x8", "wheel_size": "700c"},
    },
    {
        "category_slug": "cars_trucks",
        "title": "2006 Honda Accord EX sedan",
        "area": "south bay",
        "neighborhood": "san jose north",
        "price": 6200,
        "condition": "good",
        "description": "Accord sedan with service records, cold AC, and current registration. Title details are listed below.",
        "details": {"make": "Honda", "model": "Accord EX", "mileage": "151000", "title_status": "clean", "transmission": "automatic"},
    },
    {
        "category_slug": "cars_trucks",
        "title": "2005 Honda Civic Hybrid",
        "area": "east bay",
        "neighborhood": "oakland",
        "price": 5400,
        "condition": "good",
        "description": "Commuter Civic with recent tires and smog certificate. See detail table for title and mileage.",
        "details": {"make": "Honda", "model": "Civic Hybrid", "mileage": "178000", "title_status": "rebuilt", "transmission": "automatic"},
    },
    {
        "category_slug": "cars_trucks",
        "title": "2011 Honda Accord EX-L",
        "area": "north bay",
        "neighborhood": "santa rosa",
        "price": 6900,
        "condition": "fair",
        "description": "Leather interior and navigation. Needs suspension work soon.",
        "details": {"make": "Honda", "model": "Accord EX-L", "mileage": "189000", "title_status": "clean", "transmission": "automatic"},
    },
    {
        "category_slug": "cars_trucks",
        "title": "2008 Honda Fit manual",
        "area": "peninsula",
        "neighborhood": "redwood city",
        "price": 5900,
        "condition": "good",
        "description": "Manual hatchback with service history. Cosmetic dents on passenger door.",
        "details": {"make": "Honda", "model": "Fit", "mileage": "162000", "title_status": "clean", "transmission": "manual"},
    },
    {
        "category_slug": "cars_trucks",
        "title": "2014 Honda Odyssey EX-L",
        "area": "east bay",
        "neighborhood": "pleasanton",
        "price": 14950,
        "condition": "excellent",
        "description": "One-owner minivan with leather seats, backup camera, and recent tires.",
        "details": {"make": "Honda", "model": "Odyssey", "mileage": "103000", "title_status": "clean", "seats": "8"},
    },
    {
        "category_slug": "cars_trucks",
        "title": "Honda Passport project SUV",
        "area": "south bay",
        "neighborhood": "san jose south",
        "price": 1400,
        "condition": "fair",
        "description": "Mechanic special. Runs, but needs smog work and rear brakes.",
        "details": {"make": "Honda", "model": "Passport", "mileage": "204000", "title_status": "salvage"},
    },
    {
        "category_slug": "appliances",
        "title": "LG washer and gas dryer pair",
        "area": "east bay",
        "neighborhood": "alameda",
        "price": 380,
        "condition": "good",
        "description": "Front-load washer and gas dryer pair. Both tested before removal.",
        "details": {"washer": "front load", "dryer": "gas", "delivery": "curbside available"},
    },
    {
        "category_slug": "free",
        "title": "Free moving boxes and packing paper",
        "area": "east bay",
        "neighborhood": "oakland temescal",
        "price": 0,
        "condition": "used",
        "description": "Twenty sturdy moving boxes plus packing paper. Porch pickup after 6pm.",
        "details": {"quantity": "20 boxes", "pickup": "porch", "cross_streets": "Telegraph and 45th"},
    },
    {
        "category_slug": "apartments",
        "title": "Sunny studio near Berkeley BART",
        "area": "east bay",
        "neighborhood": "berkeley",
        "price": 2195,
        "bedrooms": 0,
        "sqft": 510,
        "description": "Top-floor studio with bike room and shared roof deck. The detail table lists laundry, lease, and pet notes.",
        "details": {"laundry": "in-unit", "parking": "street", "pet_policy": "cats ok", "lease": "12 months"},
    },
    {
        "category_slug": "apartments",
        "title": "Berkeley studio near campus",
        "area": "east bay",
        "neighborhood": "berkeley",
        "price": 2050,
        "bedrooms": 0,
        "sqft": 405,
        "description": "Small studio near transit and campus. Amenities are listed in the detail table.",
        "details": {"laundry": "shared", "parking": "none", "pet_policy": "no pets", "lease": "12 months"},
    },
    {
        "category_slug": "apartments",
        "title": "Oakland garden studio",
        "area": "east bay",
        "neighborhood": "oakland",
        "price": 1875,
        "bedrooms": 0,
        "sqft": 390,
        "description": "Garden-level studio with private entrance. Utility and laundry notes are in the detail table.",
        "details": {"laundry": "shared", "parking": "street", "pet_policy": "small dogs ok", "lease": "6 months"},
    },
    {
        "category_slug": "apartments",
        "title": "Alameda studio by the ferry",
        "area": "east bay",
        "neighborhood": "alameda",
        "price": 2310,
        "bedrooms": 0,
        "sqft": 470,
        "description": "Studio close to ferry and shoreline path. Detail table lists building amenities.",
        "details": {"laundry": "coin", "parking": "included", "pet_policy": "cats ok", "lease": "12 months"},
    },
    {
        "category_slug": "apartments",
        "title": "Emeryville studio loft",
        "area": "east bay",
        "neighborhood": "emeryville",
        "price": 2385,
        "bedrooms": 0,
        "sqft": 525,
        "description": "Open loft studio with high ceilings and secure entry. See detail table for laundry policy.",
        "details": {"laundry": "shared", "parking": "garage extra", "pet_policy": "cats ok", "lease": "12 months"},
    },
    {
        "category_slug": "apartments",
        "title": "Mission one bedroom with parking",
        "area": "san francisco",
        "neighborhood": "mission district",
        "price": 2895,
        "bedrooms": 1,
        "sqft": 650,
        "description": "One bedroom apartment with one assigned parking space and shared laundry.",
        "details": {"laundry": "shared", "parking": "included", "pet_policy": "no pets", "lease": "12 months"},
    },
    {
        "category_slug": "apartments",
        "title": "Quiet studio with courtyard view",
        "area": "peninsula",
        "neighborhood": "san mateo",
        "price": 2350,
        "bedrooms": 0,
        "sqft": 430,
        "description": "Courtyard-facing studio, renovated kitchen, no parking, coin laundry.",
        "details": {"laundry": "coin", "parking": "none", "pet_policy": "small dogs ok", "lease": "9 months"},
    },
    {
        "category_slug": "rooms_shares",
        "title": "Room in sunny Oakland craftsman",
        "area": "east bay",
        "neighborhood": "rockridge",
        "price": 1250,
        "bedrooms": 1,
        "sqft": 140,
        "description": "Room in a three-bedroom house with garden, shared kitchen, and storage for one bike.",
        "details": {"utilities": "split", "bath": "shared", "move_in": "June 1"},
    },
    {
        "category_slug": "software",
        "title": "Backend engineer for civic data startup",
        "area": "san francisco",
        "neighborhood": "soma",
        "price": None,
        "compensation": "$155k - $180k",
        "company": "Harbor Civic Labs",
        "employment_type": "full-time",
        "description": "Small team building public-record search tools. Python, Postgres, and data pipelines.",
        "details": {"remote": "hybrid", "stack": "Python Postgres Flask", "equity": "0.15%"},
    },
    {
        "category_slug": "healthcare",
        "title": "Speech language pathologist school year role",
        "area": "north bay",
        "neighborhood": "vallejo",
        "price": None,
        "compensation": "$62 - $70 per hour",
        "company": "Bay Learning Services",
        "employment_type": "contract",
        "description": "School-year clinician role with onsite team support. Detail table lists setting and license notes.",
        "details": {"schedule": "2026-2027 school year", "license": "CA SLP required", "setting": "K-8"},
    },
    {
        "category_slug": "food_bev_hosp",
        "title": "Line cook for modern Asian bistro",
        "area": "san francisco",
        "neighborhood": "richmond district",
        "price": None,
        "compensation": "$26 - $30 per hour plus tips",
        "company": "Mika Bistro",
        "employment_type": "full-time",
        "description": "Dinner service line cook, wok station helpful, two consecutive days off.",
        "details": {"shift": "3pm-11pm", "benefits": "meals transit stipend", "experience": "2 years"},
    },
    {
        "category_slug": "general_labor",
        "title": "Movers needed for weekend apartment turns",
        "area": "east bay",
        "neighborhood": "emeryville",
        "price": None,
        "compensation": "$28 per hour cash",
        "company": "Bay Move Crew",
        "employment_type": "part-time",
        "description": "Weekend work loading boxes and furniture. Must be able to lift 60 lb.",
        "details": {"schedule": "Saturday and Sunday", "start": "8am", "tools": "gloves provided"},
    },
    {
        "category_slug": "lessons",
        "title": "Remote algebra and calculus tutoring",
        "area": "san francisco",
        "neighborhood": "remote",
        "price": 55,
        "condition": "new",
        "description": "Online math lessons for high-school algebra, pre-calculus, and AP calculus.",
        "details": {"format": "Zoom", "rate": "$55 per hour", "subjects": "algebra calculus"},
    },
    {
        "category_slug": "computer_services",
        "title": "MacBook repair and data recovery",
        "area": "south bay",
        "neighborhood": "santa clara",
        "price": 90,
        "condition": "new",
        "description": "Laptop diagnostics, SSD upgrades, data migration, and screen replacement quotes.",
        "details": {"diagnostic": "$90", "turnaround": "same week", "brands": "Apple Dell Lenovo"},
    },
    {
        "category_slug": "events",
        "title": "Saturday neighborhood plant swap",
        "area": "san francisco",
        "neighborhood": "mission district",
        "price": 0,
        "condition": "new",
        "description": "Neighborhood plant swap near Dolores Park. Detail table lists the time and what to bring.",
        "details": {"date": "Saturday", "time": "10:00 AM", "bring": "labeled plants"},
    },
    {
        "category_slug": "volunteers",
        "title": "Volunteer bike repair clinic helpers",
        "area": "east bay",
        "neighborhood": "oakland",
        "price": 0,
        "condition": "new",
        "description": "Help check brakes, patch tubes, and guide neighbors through basic bike fixes.",
        "details": {"date": "Saturday", "time": "1:00 PM", "skills": "basic bike repair"},
    },
    {
        "category_slug": "artists",
        "title": "Seeking photographer for small zine project",
        "area": "south bay",
        "neighborhood": "santa clara",
        "price": 200,
        "condition": "new",
        "description": "Portrait session for a local zine. Natural light style preferred, two-hour shoot.",
        "details": {"budget": "$200", "format": "digital", "deadline": "May 24"},
    },
]


TARGET_NEAR_MISSES = [
    {"category_slug": "bikes", "title": "Commuter bike with rear rack", "area": "east bay", "neighborhood": "oakland", "price": 315, "condition": "good", "description": "Daily commuter bike with fenders and rack. Detail table lists frame and brake setup.", "details": {"frame": "medium", "brakes": "rim", "gears": "3x7", "wheel_size": "700c"}},
    {"category_slug": "bikes", "title": "Lightweight commuter bicycle", "area": "san francisco", "neighborhood": "inner sunset", "price": 440, "condition": "good", "description": "Reliable commuter for city errands. Detail table lists parts and fit.", "details": {"frame": "small", "brakes": "mechanical disc", "gears": "2x8", "wheel_size": "700c"}},
    {"category_slug": "bikes", "title": "Flat bar commuter bike", "area": "south bay", "neighborhood": "campbell", "price": 390, "condition": "fair", "description": "Flat bar commuter with lights and bottle cage. Detail table lists maintenance notes.", "details": {"frame": "large", "brakes": "rim", "gears": "1x8", "wheel_size": "700c"}},
    {"category_slug": "bikes", "title": "Commuter bike, step-through frame", "area": "peninsula", "neighborhood": "redwood city", "price": 285, "condition": "good", "description": "Comfort commuter with upright bars and kickstand.", "details": {"frame": "medium step-through", "brakes": "coaster", "gears": "7 speed", "wheel_size": "26 in"}},

    {"category_slug": "cars_trucks", "title": "2003 Honda CR-V AWD", "area": "east bay", "neighborhood": "hayward", "price": 5800, "condition": "good", "description": "Older CR-V with roof rack and current smog. Detail table lists title status.", "details": {"make": "Honda", "model": "CR-V", "mileage": "177000", "title_status": "clean", "transmission": "automatic"}},
    {"category_slug": "cars_trucks", "title": "2007 Honda Civic coupe", "area": "south bay", "neighborhood": "milpitas", "price": 4900, "condition": "fair", "description": "Civic coupe with new battery and working AC. Detail table lists paperwork.", "details": {"make": "Honda", "model": "Civic", "mileage": "201000", "title_status": "salvage", "transmission": "automatic"}},
    {"category_slug": "cars_trucks", "title": "2009 Honda Element", "area": "santa cruz", "neighborhood": "aptos", "price": 6600, "condition": "good", "description": "Element with roof bars and camping platform. Detail table lists title status.", "details": {"make": "Honda", "model": "Element", "mileage": "184000", "title_status": "clean", "transmission": "automatic"}},

    {"category_slug": "events", "title": "Succulent plant exchange", "area": "east bay", "neighborhood": "berkeley", "price": 0, "condition": "new", "description": "Casual plant exchange for cuttings and extra pots.", "details": {"date": "Sunday", "time": "11:00 AM", "bring": "small labeled cuttings"}},
    {"category_slug": "events", "title": "Houseplant swap table", "area": "north bay", "neighborhood": "san rafael", "price": 0, "condition": "new", "description": "Community table for swapping houseplants and garden starts.", "details": {"date": "Friday", "time": "4:00 PM", "bring": "healthy plants only"}},
    {"category_slug": "events", "title": "Seedling swap meetup", "area": "south bay", "neighborhood": "santa clara", "price": 0, "condition": "new", "description": "Swap vegetable seedlings and talk balcony gardening.", "details": {"date": "Saturday", "time": "9:00 AM", "bring": "seedling trays"}},
    {"category_slug": "events", "title": "Plant care workshop", "area": "san francisco", "neighborhood": "richmond district", "price": 0, "condition": "new", "description": "Beginner workshop on repotting and watering indoor plants.", "details": {"date": "Thursday", "time": "6:30 PM", "bring": "one problem plant"}},

    {"category_slug": "free", "title": "Free wardrobe boxes", "area": "east bay", "neighborhood": "berkeley", "price": 0, "condition": "used", "description": "Tall moving boxes from a recent apartment move.", "details": {"quantity": "6 wardrobe boxes", "pickup": "curb", "cross_streets": "Shattuck and Dwight"}},
    {"category_slug": "free", "title": "Moving boxes and bubble wrap", "area": "east bay", "neighborhood": "alameda", "price": 0, "condition": "used", "description": "Stack of moving boxes, paper, and bubble wrap.", "details": {"quantity": "12 boxes", "pickup": "garage", "cross_streets": "Park and Lincoln"}},
    {"category_slug": "free", "title": "Small boxes for books", "area": "east bay", "neighborhood": "emeryville", "price": 0, "condition": "used", "description": "Free small book boxes from a move.", "details": {"quantity": "15 boxes", "pickup": "lobby", "cross_streets": "40th and Hollis"}},
    {"category_slug": "free", "title": "Flattened moving boxes", "area": "east bay", "neighborhood": "oakland", "price": 0, "condition": "used", "description": "Flattened moving boxes, clean and dry.", "details": {"quantity": "18 boxes", "pickup": "porch", "cross_streets": "Broadway and 51st"}},

    {"category_slug": "healthcare", "title": "Pediatric speech language assistant", "area": "south bay", "neighborhood": "campbell", "price": None, "compensation": "$38 - $45 per hour", "company": "Bright Steps Therapy", "employment_type": "part-time", "description": "Clinic support role for pediatric speech therapy sessions.", "details": {"schedule": "3 weekdays", "license": "SLPA preferred", "setting": "clinic"}},
    {"category_slug": "healthcare", "title": "Speech therapist telehealth contract", "area": "san francisco", "neighborhood": "remote", "price": None, "compensation": "$58 per hour", "company": "Remote Learning Care", "employment_type": "contract", "description": "Online speech therapy sessions for middle-school students.", "details": {"schedule": "August-May", "license": "CA SLP required", "setting": "telehealth"}},
    {"category_slug": "healthcare", "title": "Language development aide", "area": "east bay", "neighborhood": "oakland", "price": None, "compensation": "$31 per hour", "company": "Oakland Child Services", "employment_type": "full-time", "description": "Support language development programs under clinician supervision.", "details": {"schedule": "school year", "license": "associate permit", "setting": "preschool"}},
    {"category_slug": "healthcare", "title": "School occupational therapist", "area": "peninsula", "neighborhood": "san mateo", "price": None, "compensation": "$65 per hour", "company": "Bay School Staffing", "employment_type": "contract", "description": "School therapist role with elementary caseload.", "details": {"schedule": "2026-2027 school year", "license": "CA OT required", "setting": "K-5"}},

    {"category_slug": "lessons", "title": "Online math tutoring for algebra", "area": "san francisco", "neighborhood": "remote", "price": 45, "condition": "new", "description": "Remote math tutoring for algebra and geometry.", "details": {"format": "Zoom", "rate": "$45 per hour", "subjects": "algebra geometry"}},
    {"category_slug": "lessons", "title": "Calculus tutoring, weekends", "area": "peninsula", "neighborhood": "palo alto", "price": 70, "condition": "new", "description": "Weekend tutoring for calculus and statistics.", "details": {"format": "library or online", "rate": "$70 per hour", "subjects": "calculus statistics"}},
    {"category_slug": "lessons", "title": "SAT math tutor", "area": "east bay", "neighborhood": "berkeley", "price": 60, "condition": "new", "description": "SAT math prep with practice tests.", "details": {"format": "in person", "rate": "$60 per hour", "subjects": "SAT math"}},
    {"category_slug": "lessons", "title": "Middle school math tutoring", "area": "south bay", "neighborhood": "sunnyvale", "price": 50, "condition": "new", "description": "Patient math tutoring for middle school students.", "details": {"format": "online", "rate": "$50 per hour", "subjects": "pre-algebra"}},

    {"category_slug": "labor_move", "title": "Moving help for apartments", "area": "east bay", "neighborhood": "oakland", "price": 80, "condition": "new", "description": "Two helpers for local apartment moving jobs.", "details": {"crew": "2 people", "rate": "$80 per hour", "truck": "not included"}},
    {"category_slug": "labor_move", "title": "Small moving crew with blankets", "area": "san francisco", "neighborhood": "mission district", "price": 110, "condition": "new", "description": "Moving crew for furniture, boxes, and studio apartments.", "details": {"crew": "2 people", "rate": "$110 per hour", "truck": "cargo van"}},
    {"category_slug": "labor_move", "title": "Last minute moving labor", "area": "south bay", "neighborhood": "san jose", "price": 75, "condition": "new", "description": "Labor-only moving help for stairs and loading.", "details": {"crew": "1-2 people", "rate": "$75 per hour", "truck": "not included"}},
    {"category_slug": "labor_move", "title": "Weekend moving and hauling", "area": "peninsula", "neighborhood": "san mateo", "price": 125, "condition": "new", "description": "Weekend moving and hauling for small households.", "details": {"crew": "2 people", "rate": "$125 per hour", "truck": "box truck"}},

    {"category_slug": "electronics", "title": "LG USB-C monitor", "area": "east bay", "neighborhood": "berkeley", "price": 190, "condition": "good", "description": "USB-C display with stand and cable. Detail table lists specs.", "details": {"size": "24 in", "resolution": "1920x1080", "ports": "USB-C HDMI"}},
    {"category_slug": "electronics", "title": "BenQ office monitor", "area": "san francisco", "neighborhood": "nopa", "price": 95, "condition": "good", "description": "Office monitor with stand. Detail table lists specs.", "details": {"size": "27 in", "resolution": "1920x1080", "ports": "HDMI DP"}},
    {"category_slug": "electronics", "title": "Portable USB-C display", "area": "south bay", "neighborhood": "santa clara", "price": 145, "condition": "like new", "description": "Slim portable display with sleeve. Detail table lists specs.", "details": {"size": "15.6 in", "resolution": "1920x1080", "ports": "USB-C mini-HDMI"}},
    {"category_slug": "electronics", "title": "Ultrawide monitor with USB hub", "area": "peninsula", "neighborhood": "san mateo", "price": 260, "condition": "good", "description": "Large monitor with built-in hub. Detail table lists specs.", "details": {"size": "34 in", "resolution": "3440x1440", "ports": "HDMI DP USB-A"}},

    {"category_slug": "volunteers", "title": "Bike lane cleanup volunteers", "area": "east bay", "neighborhood": "oakland", "price": 0, "condition": "new", "description": "Volunteers needed for weekend bike lane cleanup.", "details": {"date": "Sunday", "time": "9:30 AM", "skills": "comfortable outdoors"}},
    {"category_slug": "volunteers", "title": "Community repair cafe volunteers", "area": "san francisco", "neighborhood": "haight", "price": 0, "condition": "new", "description": "Repair cafe seeks volunteers for small household fixes.", "details": {"date": "Saturday", "time": "2:00 PM", "skills": "basic hand tools"}},
    {"category_slug": "volunteers", "title": "Youth bike rodeo helpers", "area": "south bay", "neighborhood": "santa clara", "price": 0, "condition": "new", "description": "Help kids practice bike safety at a neighborhood event.", "details": {"date": "Saturday", "time": "10:30 AM", "skills": "patience with kids"}},
    {"category_slug": "volunteers", "title": "Tool library repair shift", "area": "east bay", "neighborhood": "berkeley", "price": 0, "condition": "new", "description": "Volunteer shift repairing donated tools and sorting parts.", "details": {"date": "Wednesday", "time": "5:00 PM", "skills": "basic repair"}},
    {"category_slug": "events", "title": "Plant swap picnic table", "area": "peninsula", "neighborhood": "san mateo", "price": 0, "condition": "new", "description": "Small plant swap hosted at a public picnic table.", "details": {"date": "Sunday", "time": "3:00 PM", "bring": "pest-free cuttings"}},
    {"category_slug": "free", "title": "Free boxes for moving day", "area": "east bay", "neighborhood": "richmond", "price": 0, "condition": "used", "description": "Assorted free boxes left from moving day.", "details": {"quantity": "10 boxes", "pickup": "driveway", "cross_streets": "23rd and Barrett"}},
    {"category_slug": "apartments", "title": "West Oakland studio apartment", "area": "east bay", "neighborhood": "west oakland", "price": 2225, "bedrooms": 0, "sqft": 455, "condition": "new", "description": "Compact studio apartment close to BART. Detail table lists laundry and parking notes.", "details": {"laundry": "shared", "parking": "street", "pet_policy": "no pets", "lease": "12 months"}},
    {"category_slug": "healthcare", "title": "Travel speech pathologist opening", "area": "north bay", "neighborhood": "napa", "price": None, "compensation": "$61 per hour", "company": "North Bay Therapy", "employment_type": "contract", "description": "Travel speech clinician opening with district team support.", "details": {"schedule": "fall semester", "license": "CA SLP required", "setting": "high school"}},
    {"category_slug": "healthcare", "title": "Bilingual language pathologist", "area": "east bay", "neighborhood": "fremont", "price": None, "compensation": "$64 per hour", "company": "Fremont Student Services", "employment_type": "full-time", "description": "Bilingual language services role with onsite supervision.", "details": {"schedule": "school calendar", "license": "CA SLP or RPE", "setting": "elementary"}},
    {"category_slug": "lessons", "title": "AP math tutoring online", "area": "north bay", "neighborhood": "remote", "price": 58, "condition": "new", "description": "Online tutoring for AP math courses and exam review.", "details": {"format": "Zoom", "rate": "$58 per hour", "subjects": "AP calculus pre-calculus"}},
    {"category_slug": "labor_move", "title": "Moving help with pickup truck", "area": "north bay", "neighborhood": "san rafael", "price": 90, "condition": "new", "description": "Small moving jobs with one pickup truck and blankets.", "details": {"crew": "2 people", "rate": "$90 per hour", "truck": "pickup"}},
    {"category_slug": "labor_move", "title": "Apartment moving and packing", "area": "east bay", "neighborhood": "berkeley", "price": 100, "condition": "new", "description": "Apartment moving, packing help, and loading support.", "details": {"crew": "2 people", "rate": "$100 per hour", "truck": "van available"}},
    {"category_slug": "volunteers", "title": "Bike repair table volunteers", "area": "east bay", "neighborhood": "emeryville", "price": 0, "condition": "new", "description": "Volunteers needed at a bike repair information table.", "details": {"date": "Sunday", "time": "12:00 PM", "skills": "friendly with cyclists"}},
    {"category_slug": "volunteers", "title": "Community bike repair setup crew", "area": "east bay", "neighborhood": "berkeley", "price": 0, "condition": "new", "description": "Volunteers help set up stands and check in neighbors for a bike repair afternoon.", "details": {"date": "Saturday", "time": "11:00 AM", "skills": "event setup"}},
    {"category_slug": "volunteers", "title": "Bike day repair station helpers", "area": "east bay", "neighborhood": "oakland", "price": 0, "condition": "new", "description": "Repair station seeks helpers for basic intake, tools, and sign-in during bike day.", "details": {"date": "Saturday", "time": "3:30 PM", "skills": "organized with tools"}},
]


EXTRA_BLUEPRINTS = {
    "furniture": [
        ("Maple bookcase with adjustable shelves", 95, "good", "solid wood bookcase, light scratches"),
        ("Round kitchen table with four chairs", 180, "good", "small dining set for apartment"),
        ("Blue loveseat, pet-free home", 160, "excellent", "comfortable loveseat, no stains"),
        ("Metal filing cabinet, two drawer", 45, "fair", "office cabinet with working lock"),
        ("Queen bed frame with slats", 110, "good", "platform bed frame, no mattress"),
        ("Glass coffee table", 70, "good", "thick glass top, chrome legs"),
    ],
    "electronics": [
        ("iPad Air with keyboard case", 310, "excellent", "tablet, charger, and case"),
        ("Nintendo Switch bundle", 240, "good", "console, dock, two controllers"),
        ("Eero mesh router three pack", 120, "good", "whole-home wifi kit"),
        ("Bose bookshelf speakers", 175, "good", "pair of compact speakers"),
        ("Logitech webcam and ring light", 55, "like new", "video call setup"),
    ],
    "bikes": [
        ("Cannondale road bike, 54cm", 690, "excellent", "aluminum road bike with carbon fork"),
        ("Folding bike for Caltrain commute", 375, "good", "compact folding bike with rear rack"),
        ("Kids bike, 20 inch wheels", 80, "good", "recent tubes and training stand"),
        ("Single speed city bike", 220, "fair", "simple commuter with new tires"),
    ],
    "apartments": [
        ("Pet friendly one bedroom near Lake Merritt", 2475, "new", "balcony, dishwasher, shared laundry"),
        ("South Bay studio with gated parking", 2250, "new", "studio apartment with covered parking"),
        ("North Beach two bedroom flat", 3650, "new", "classic flat near restaurants"),
        ("Garden level in-law apartment", 1980, "new", "private entrance, utilities included"),
        ("Sunny room in shared Mission apartment", 1390, "new", "shared kitchen and roof access"),
    ],
    "jobs": [
        ("Customer support specialist, hybrid", None, "new", "help members by phone and email"),
        ("Part-time barista morning shifts", None, "new", "espresso service and register"),
        ("Senior contact center engineer", None, "new", "maintain cloud telephony systems"),
        ("Painter apprentice, all levels", None, "new", "residential repaint crew"),
        ("Youth tennis coach needed", None, "new", "after-school tennis program"),
        ("Registered nurse floater", None, "new", "clinic float role across East Bay"),
    ],
    "services": [
        ("Two-person moving help with van", 95, "new", "local moves, stairs ok"),
        ("Guitar lessons for beginners", 45, "new", "weekly lessons in person or online"),
        ("House cleaning, green supplies", 120, "new", "apartments and small homes"),
        ("Logo design for small businesses", 250, "new", "brand kit and social avatars"),
    ],
    "community": [
        ("East Bay board game night", 0, "new", "weekly strategy games and snacks"),
        ("Lost gray tabby cat near Panhandle", 0, "new", "microchipped gray tabby"),
        ("Figure drawing group seeking models", 0, "new", "weekly session with easels"),
        ("Free compost workshop", 0, "new", "learn balcony compost basics"),
    ],
}


def build_listing_records(base_dir):
    pools = image_pool(base_dir)
    records = []

    for i, item in enumerate(SPECIAL_LISTINGS):
        row = dict(item)
        row["image"] = pick_image(pools, row["category_slug"], i)
        records.append(finalize_record(row, pools, i))

    offset = len(records)
    for i, item in enumerate(TARGET_NEAR_MISSES, start=1):
        row = dict(item)
        row["image"] = pick_image(pools, row["category_slug"], offset + i)
        records.append(finalize_record(row, pools, offset + i))

    category_sequence = [
        ("furniture", "for_sale"),
        ("electronics", "for_sale"),
        ("bikes", "for_sale"),
        ("apartments", "housing"),
        ("rooms_shares", "housing"),
        ("sublets", "housing"),
        ("parking", "housing"),
        ("office_commercial", "housing"),
        ("software", "jobs"),
        ("customer_service", "jobs"),
        ("food_bev_hosp", "jobs"),
        ("general_labor", "jobs"),
        ("healthcare", "jobs"),
        ("education", "jobs"),
        ("automotive_services", "services"),
        ("computer_services", "services"),
        ("household_services", "services"),
        ("labor_move", "services"),
        ("lessons", "services"),
        ("events", "community"),
        ("volunteers", "community"),
        ("artists", "community"),
        ("groups", "community"),
        ("lost_found", "community"),
    ]
    area_cycle = REGIONS
    neighborhood_cycle = [
        "berkeley", "oakland", "mission district", "palo alto", "san jose",
        "san mateo", "santa rosa", "santa cruz", "alameda", "sunnyvale",
    ]

    idx = 0
    for category_slug, group in category_sequence:
        if category_slug in EXTRA_BLUEPRINTS:
            blueprints = EXTRA_BLUEPRINTS[category_slug]
        elif group in EXTRA_BLUEPRINTS:
            blueprints = EXTRA_BLUEPRINTS[group]
        elif group == "jobs":
            blueprints = EXTRA_BLUEPRINTS["jobs"]
        elif group == "services":
            blueprints = EXTRA_BLUEPRINTS["services"]
        else:
            blueprints = EXTRA_BLUEPRINTS["community"]
        for title, price, condition, desc in blueprints[:4]:
            idx += 1
            row = {
                "category_slug": category_slug,
                "title": title,
                "area": area_cycle[idx % len(area_cycle)],
                "neighborhood": neighborhood_cycle[idx % len(neighborhood_cycle)],
                "price": price,
                "condition": condition,
                "description": desc + ". Contact by email for details.",
                "details": {
                    "posted_by": "owner",
                    "availability": "available now",
                    "cross_streets": neighborhood_cycle[(idx + 2) % len(neighborhood_cycle)],
                },
                "image": pick_image(pools, category_slug, idx),
            }
            records.append(finalize_record(row, pools, idx))
    return records


def seed_categories(db, Category):
    if Category.query.count() > 0:
        return
    order = 0
    for group in CATEGORY_GROUPS:
        for slug, name, abbrev in group["columns"]:
            order += 1
            db.session.add(Category(
                slug=slug,
                name=name,
                abbrev=abbrev,
                group_slug=group["slug"],
                group_name=group["name"],
                display_order=order,
            ))
    db.session.commit()


def seed_database(base_dir, db, Category, Listing):
    if Listing.query.count() > 0:
        return
    seed_categories(db, Category)
    category_map = {c.slug: c for c in Category.query.all()}
    records = build_listing_records(base_dir)
    for idx, row in enumerate(records, start=1):
        category = category_map[row["category_slug"]]
        title = row["title"]
        listing = Listing(
            title=title,
            slug=f"{slugify(title)}-{idx}",
            category_id=category.id,
            category_slug=category.slug,
            category_group=category.group_slug,
            area=row.get("area", REGIONS[idx % len(REGIONS)]),
            neighborhood=row.get("neighborhood", "san francisco"),
            price=row.get("price"),
            bedrooms=row.get("bedrooms"),
            sqft=row.get("sqft"),
            condition=row.get("condition", ""),
            compensation=row.get("compensation", ""),
            company=row.get("company", ""),
            employment_type=row.get("employment_type", ""),
            description=row.get("description", ""),
            details_json=json.dumps(row.get("details", {}), sort_keys=True),
            image=row.get("image", ""),
            seller_name=row.get("seller_name", "craigslist user"),
            seller_email=row.get("seller_email", f"reply{idx}@example.test"),
            reply_phone=row.get("reply_phone", ""),
            posted_at=FIXED_NOW - timedelta(hours=idx * 3),
            updated_at=FIXED_NOW - timedelta(hours=idx * 2),
            status="active",
        )
        db.session.add(listing)
    db.session.commit()


def seed_benchmark_users(db, User, Listing, SavedListing, SavedSearch, Message):
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    users = [
        ("alice.j@test.com", "Alice Johnson", "alice", "san francisco"),
        ("ben.k@test.com", "Ben Kim", "ben", "east bay"),
        ("carla.m@test.com", "Carla Martinez", "carla", "south bay"),
        ("david.p@test.com", "David Patel", "david", "peninsula"),
    ]
    created = []
    for email, name, username, area in users:
        user = User(
            email=email,
            username=username,
            name=name,
            area=area,
            phone="(415) 555-0100",
            password_hash=deterministic_password(email),
            created_at=FIXED_NOW - timedelta(days=45),
        )
        db.session.add(user)
        created.append(user)
    db.session.flush()

    alice = created[0]
    desk = Listing.query.filter(Listing.title.ilike("%task chair%")).first()
    accord = Listing.query.filter(Listing.title.ilike("%Accord%")).first()
    studio = Listing.query.filter(Listing.title.ilike("%Berkeley BART%")).first()
    for listing in [desk, accord, studio]:
        if listing:
            db.session.add(SavedListing(
                user_id=alice.id,
                listing_id=listing.id,
                note="compare before contacting",
                created_at=FIXED_NOW - timedelta(days=2),
            ))

    db.session.add(SavedSearch(
        user_id=alice.id,
        name="East Bay furniture under 100",
        query_text="chair desk",
        category_slug="furniture",
        area="east bay",
        max_price=100,
        created_at=FIXED_NOW - timedelta(days=3),
    ))
    db.session.add(SavedSearch(
        user_id=alice.id,
        name="Studios with laundry",
        query_text="studio laundry",
        category_slug="apartments",
        area="east bay",
        max_price=2400,
        created_at=FIXED_NOW - timedelta(days=1),
    ))

    if studio:
        db.session.add(Message(
            user_id=alice.id,
            listing_id=studio.id,
            sender_name="Leasing office",
            sender_email="leasing@example.test",
            body="The Berkeley studio can be shown Wednesday at 5:30pm or Thursday at noon.",
            direction="inbound",
            created_at=FIXED_NOW - timedelta(hours=18),
            is_read=False,
        ))
    if accord:
        db.session.add(Message(
            user_id=alice.id,
            listing_id=accord.id,
            sender_name="Alice Johnson",
            sender_email="alice.j@test.com",
            body="Hi, is the Accord still available and can I see service records?",
            direction="outbound",
            created_at=FIXED_NOW - timedelta(hours=10),
            is_read=True,
        ))

    db.session.commit()
