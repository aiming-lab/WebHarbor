"""Deterministic source catalog for the Walmart Careers mirror.

Every posting in the mirror is generated from this file: title families with an
explicit list of placements (store, employment type, shifts, pay band, open
positions). Body copy comes from per-family templates with slot fills, so the
200 postings stay internally consistent without 200 hand-written essays.

Nothing here is read at request time. `seed_data.py` turns it into SQLite rows.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# Areas
# --------------------------------------------------------------------------- #
# (slug, name, display_order, blurb, hero_image, has_index_page, is_filterable)
AREAS = [
    (
        "stores-and-clubs",
        "Stores and Clubs",
        1,
        "Find your path with us. Whether you're interested in auto care, front-end services, "
        "general merchandising, or another team, you'll find opportunities to grow and the "
        "support to reach your career goals.",
        "area-stores.jpg",
        True,
        True,
    ),
    (
        "supply-chain-and-transportation",
        "Supply Chain and Transportation",
        2,
        "Move product, move people forward. Our distribution centers, fulfillment centers and "
        "private fleet keep shelves stocked and orders on time across the country.",
        "area-supply-chain.jpg",
        True,
        True,
    ),
    (
        "healthcare",
        "Healthcare",
        3,
        "Care that reaches everyone. Our pharmacy, vision and wellness teams serve millions of "
        "neighbours every week, right inside the stores they already shop.",
        "area-healthcare.jpg",
        True,
        True,
    ),
    (
        "technology",
        "Technology",
        4,
        "At Walmart and Sam's Club, we are people-led, tech-powered. Everything you build here - "
        "from smarter supply chains to seamless shopping - starts with real needs and creates "
        "real impact.",
        "area-technology.jpg",
        True,
        True,
    ),
    (
        "corporate",
        "Corporate",
        5,
        "Strategy, finance, merchandising, marketing and people teams that set the direction for "
        "the world's largest retailer.",
        "area-corporate.jpg",
        True,
        True,
    ),
    (
        "students",
        "Students",
        6,
        "Internships and early career programs across every part of the business.",
        "area-students.png",
        False,
        True,
    ),
    (
        "Military",
        "Military",
        7,
        "Your service prepared you to lead. Bring that experience to a company that hires "
        "thousands of veterans, transitioning service members and military spouses every year.",
        "area-military.jpg",
        True,
        False,
    ),
]

# (area_slug, category_name, category_slug, display_order)
CATEGORIES = [
    ("stores-and-clubs", "Cashier and Front-End Services", "cashier-and-front-end-services", 1),
    ("stores-and-clubs", "Food and Grocery", "food-and-grocery", 2),
    ("stores-and-clubs", "General Merchandise, Stocking, and Unloading", "general-merchandise-stocking-and-unloading", 3),
    ("stores-and-clubs", "Digital Pickup and Delivery", "digital-pickup-and-delivery", 4),
    ("stores-and-clubs", "Cafe", "cafe", 5),
    ("stores-and-clubs", "Retail Management", "retail-management", 6),
    ("stores-and-clubs", "Fuel Station", "fuel-station", 7),
    ("stores-and-clubs", "Auto Care Center", "auto-care-center", 8),
    ("stores-and-clubs", "Auto Services", "auto-services", 9),
    ("stores-and-clubs", "Maintenance", "maintenance", 10),
    ("stores-and-clubs", "Security and Asset Protection", "security-and-asset-protection", 11),
    ("supply-chain-and-transportation", "SC&T Operations", "sct-operations", 1),
    ("supply-chain-and-transportation", "Drivers", "drivers", 2),
    ("supply-chain-and-transportation", "Engineering", "engineering", 3),
    ("supply-chain-and-transportation", "Aviation", "aviation", 4),
    ("supply-chain-and-transportation", "Security and Asset Protection", "sct-security-and-asset-protection", 5),
    ("healthcare", "Pharmacy Services", "pharmacy-services", 1),
    ("healthcare", "Optical Services", "optical-services", 2),
    ("healthcare", "Health and Wellness Operations", "health-and-wellness-operations", 3),
    ("healthcare", "Clinical Care", "clinical-care", 4),
    ("technology", "Software Engineering and Architecture", "software-engineering-and-architecture", 1),
    ("technology", "Product Management", "product-management", 2),
    ("technology", "Data Science and Analytics", "data-science-and-analytics", 3),
    ("technology", "Information Security", "information-security", 4),
    ("technology", "Creative Design and UX", "creative-design-and-ux", 5),
    ("technology", "Technical Program Management", "technical-program-management", 6),
    ("technology", "Information Technology", "information-technology", 7),
    ("corporate", "Accounting and Finance", "accounting-and-finance", 1),
    ("corporate", "Human Resources", "human-resources", 2),
    ("corporate", "Marketing and Advertising", "marketing-and-advertising", 3),
    ("corporate", "Merchandising", "merchandising", 4),
    ("corporate", "Business Operations", "business-operations", 5),
    ("students", "Internship", "internship", 1),
]

# --------------------------------------------------------------------------- #
# Stores  (store_number, banner, location_name, street, city, state, zip,
#          lat, lng, is_hub, is_office, brand)
# --------------------------------------------------------------------------- #
STORES = [
    # --- offices -----------------------------------------------------------
    ("10101", "Home Office", "WALMART HOME OFFICE", "702 SW 8th St", "Bentonville", "AR", "72716-0000", 36.363430, -94.219970, True, True, "Walmart"),
    ("11807", "Home Office", "SUNNYVALE TECH CORNERS BLDG 6", "811 11th Ave", "Sunnyvale", "CA", "94089-4731", 37.402869, -122.036132, True, True, "Walmart"),
    ("11003", "Home Office", "HOBOKEN TECH HUB", "221 River St", "Hoboken", "NJ", "07030-5989", 40.735657, -74.030324, True, True, "Walmart"),
    ("11500", "Home Office", "DALLAS METRO OFFICE", "603 Munger Ave", "Dallas", "TX", "75202-3505", 32.784618, -96.796851, True, True, "Walmart"),
    ("11109", "Home Office", "SAM'S CLUB HOME OFFICE", "2101 SE Simple Savings Dr", "Bentonville", "AR", "72712-4304", 36.343100, -94.196000, False, True, "Sam's Club"),
    ("12200", "Vizio Campus", "VIZIO IRVINE CAMPUS", "39 Tesla", "Irvine", "CA", "92618-4603", 33.650800, -117.744400, False, True, "Vizio"),
    # --- Arkansas ----------------------------------------------------------
    ("5260", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #5260", "1400 SE Walton Blvd", "Bentonville", "AR", "72712-6220", 36.354900, -94.202500, False, False, "Walmart"),
    ("144", "WM Supercenter", "WM SUPERCENTER #144", "2110 W Walnut St", "Rogers", "AR", "72756-3611", 36.334100, -94.152800, False, False, "Walmart"),
    ("8259", "Sam's Club", "SAM'S CLUB #8259", "1101 SE Walton Blvd", "Bentonville", "AR", "72712-6191", 36.357800, -94.199200, False, False, "Sam's Club"),
    ("8155", "Sam's Club", "SAM'S CLUB #8155", "3081 N College Ave", "Fayetteville", "AR", "72703-5100", 36.101000, -94.158000, False, False, "Sam's Club"),
    # --- California --------------------------------------------------------
    ("9054", "eComm Whse Logistics", "ECOMM WHSE LOGISTICS #9054", "1290 W Henderson Ave", "Porterville", "CA", "93257-5969", 36.070300, -119.041800, False, False, "Walmart"),
    ("2050", "WM Supercenter", "WM SUPERCENTER #2050", "3680 W Shaw Ave", "Fresno", "CA", "93711-3204", 36.808900, -119.828600, False, False, "Walmart"),
    ("6608", "Sam's Club", "SAM'S CLUB #6608", "5205 Monterey Hwy", "San Jose", "CA", "95111-4106", 37.259700, -121.816200, False, False, "Sam's Club"),
    # --- New Jersey --------------------------------------------------------
    ("2110", "WM Supercenter", "WM SUPERCENTER #2110", "400 Park Plaza Dr", "Secaucus", "NJ", "07094-3661", 40.786600, -74.061800, False, False, "Walmart"),
    ("3520", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #3520", "2100 88th St", "North Bergen", "NJ", "07047-4720", 40.792400, -74.011200, False, False, "Walmart"),
    # --- Texas -------------------------------------------------------------
    ("9399", "eComm Whse Logistics", "ECOMM WHSE LOGISTICS #9399", "3401 Quincy St", "Plainview", "TX", "79072-3308", 34.164300, -101.700900, False, False, "Walmart"),
    ("4750", "Sam's Club", "SAM'S CLUB #4750", "3000 E Plano Pkwy", "Plano", "TX", "75074-7440", 33.017200, -96.671900, False, False, "Sam's Club"),
    ("471", "WM Supercenter", "WM SUPERCENTER #471", "4215 Canyon Dr", "Amarillo", "TX", "79110-1109", 35.166900, -101.850700, False, False, "Walmart"),
    ("3826", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #3826", "1521 N Cockrell Hill Rd", "Dallas", "TX", "75211-7407", 32.779000, -96.887000, False, False, "Walmart"),
    # --- Florida -----------------------------------------------------------
    ("3387", "WM Supercenter", "WM SUPERCENTER #3387", "17000 Toledo Blade Blvd", "North Port", "FL", "34287-7281", 27.056300, -82.183200, False, False, "Walmart"),
    ("6318", "Sam's Club", "SAM'S CLUB #6318", "4763 Millenia Plaza Way", "Orlando", "FL", "32839-6014", 28.485600, -81.430200, False, False, "Sam's Club"),
    ("7133", "Regional DC", "REGIONAL DISTRIBUTION CENTER #7133", "3001 Bartow Rd", "Lakeland", "FL", "33803-6413", 27.981100, -81.930100, False, False, "Walmart"),
    # --- Ohio --------------------------------------------------------------
    ("2073", "WM Supercenter", "WM SUPERCENTER #2073", "10000 Brookpark Rd", "Cleveland", "OH", "44130-1102", 41.409300, -81.786600, False, False, "Walmart"),
    ("5388", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #5388", "6594 Ridge Rd", "Parma", "OH", "44129-5546", 41.387000, -81.748000, False, False, "Walmart"),
    ("6636", "Sam's Club", "SAM'S CLUB #6636", "3950 W Dublin Granville Rd", "Columbus", "OH", "43235-2701", 40.098700, -83.083100, False, False, "Sam's Club"),
    ("5439", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #5439", "5821 W Central Ave", "Toledo", "OH", "43615-2159", 41.673900, -83.673400, False, False, "Walmart"),
    ("2075", "WM Supercenter", "WM SUPERCENTER #2075", "8585 Pearl Rd", "Strongsville", "OH", "44136-1618", 41.314000, -81.829000, False, False, "Walmart"),
    ("5133", "WM Supercenter", "WM SUPERCENTER #5133", "24801 Brookpark Rd", "North Olmsted", "OH", "44070-3407", 41.429000, -81.916000, False, False, "Walmart"),
    ("4744", "Sam's Club", "SAM'S CLUB #4744", "3560 Steelyard Dr", "Cleveland", "OH", "44109-2101", 41.458600, -81.688900, False, False, "Sam's Club"),
    # --- New York ----------------------------------------------------------
    ("9046", "eComm Whse Logistics", "ECOMM WHSE LOGISTICS #9046", "8827 Old River Rd", "Marcy", "NY", "13403-3030", 43.173965, -75.315183, False, False, "Walmart"),
    ("6038", "Regional DC", "REGIONAL DISTRIBUTION CENTER #6038", "5000 Halsey Rd", "Marcy", "NY", "13403-2317", 43.155900, -75.297400, False, False, "Walmart"),
    ("2163", "WM Supercenter", "WM SUPERCENTER #2163", "1490 Hudson Ave", "Rochester", "NY", "14621-2404", 43.201800, -77.586300, False, False, "Walmart"),
    # --- Kansas ------------------------------------------------------------
    ("5991", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #5991", "2441 S Rock Rd", "Wichita", "KS", "67207-3254", 37.653900, -97.240100, False, False, "Walmart"),
    ("1179", "WM Supercenter", "WM SUPERCENTER #1179", "1301 SW Wanamaker Rd", "Topeka", "KS", "66604-3843", 39.032200, -95.762700, False, False, "Walmart"),
    ("6014", "Regional DC", "REGIONAL DISTRIBUTION CENTER #6014", "2101 S Princeton St", "Ottawa", "KS", "66067-8501", 38.588600, -95.263700, False, False, "Walmart"),
    # --- Mississippi -------------------------------------------------------
    ("954", "WM Supercenter", "WM SUPERCENTER #954", "1266 Highway 51 N", "Hazlehurst", "MS", "39083-2217", 31.879400, -90.397300, False, False, "Walmart"),
    ("1230", "WM Supercenter", "WM SUPERCENTER #1230", "1130 Brookway Blvd", "Brookhaven", "MS", "39601-3211", 31.556600, -90.443800, False, False, "Walmart"),
    ("8253", "Sam's Club", "SAM'S CLUB #8253", "6360 Ridgewood Ct Dr", "Jackson", "MS", "39211-3520", 32.393200, -90.140800, False, False, "Sam's Club"),
    # --- Iowa --------------------------------------------------------------
    ("9281", "eComm Whse Logistics", "ECOMM WHSE LOGISTICS #9281", "2600 Iris Rd", "Mount Pleasant", "IA", "52641-3106", 40.966400, -91.549600, False, False, "Walmart"),
    ("1236", "WM Supercenter", "WM SUPERCENTER #1236", "5101 SE 14th St", "Des Moines", "IA", "50320-2201", 41.531700, -93.596800, False, False, "Walmart"),
    # --- Washington --------------------------------------------------------
    ("4137", "WM Supercenter", "WM SUPERCENTER #4137", "1965 S Union Ave", "Tacoma", "WA", "98405-1615", 47.242300, -122.484500, False, False, "Walmart"),
    ("6216", "Sam's Club", "SAM'S CLUB #6216", "9950 N Newport Hwy", "Spokane", "WA", "99218-1240", 47.741400, -117.400600, False, False, "Sam's Club"),
    ("5382", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #5382", "8102 Evergreen Way", "Everett", "WA", "98203-6428", 47.905400, -122.229900, False, False, "Walmart"),
    ("7021", "Regional DC", "REGIONAL DISTRIBUTION CENTER #7021", "1300 Wine Country Rd", "Grandview", "WA", "98930-9704", 46.254000, -119.901000, False, False, "Walmart"),
    # --- Puerto Rico -------------------------------------------------------
    ("2503", "WM Supercenter", "WM SUPERCENTER #2503", "Carr 2 KM 11.4", "Bayamon", "PR", "00959-5100", 18.394200, -66.155300, False, False, "Walmart"),
    ("2610", "WM Supercenter", "WM SUPERCENTER #2610", "500 Ave Rafael Cordero", "Caguas", "PR", "00725-3607", 18.245600, -66.036200, False, False, "Walmart"),
    ("3512", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #3512", "2000 Ave Las Americas", "Ponce", "PR", "00717-0777", 18.019800, -66.612600, False, False, "Walmart"),
    ("8763", "Sam's Club", "SAM'S CLUB #8763", "100 Ave Fragoso", "Carolina", "PR", "00979-1234", 18.417400, -65.977300, False, False, "Sam's Club"),
    ("3593", "Neighborhood Market", "WM NEIGHBORHOOD MARKET #3593", "65 Ave De Diego", "San Juan", "PR", "00927-3300", 18.398500, -66.055300, False, False, "Walmart"),
    # --- Virginia ----------------------------------------------------------
    ("1399", "WM Supercenter", "WM SUPERCENTER #1399", "1123 E Lynchburg Salem Tpke", "Bedford", "VA", "24523-3446", 37.323200, -79.502400, False, False, "Walmart"),
    ("6088", "Import", "IMPORT DISTRIBUTION CENTER #6088", "8109 Merrimac Trail", "Williamsburg", "VA", "23185-6255", 37.288600, -76.664900, False, False, "Walmart"),
]

# --------------------------------------------------------------------------- #
# Shifts
# --------------------------------------------------------------------------- #
SHIFT_CODES = {
    "WD": "Weekday Day",
    "WE": "Weekday Evening",
    "WN": "Weekday Overnight",
    "SD": "Weekend Day",
    "SE": "Weekend Evening",
    "SN": "Weekend Overnight",
    "FX": "Flex",
}
SHIFT_WINDOWS = {
    "WD": "Shift may start between 6:00am - 11:00am",
    "WE": "Shift may start between 12:00pm - 5:00pm",
    "WN": "Shift may start between 8:00pm - 1:00am",
    "SD": "Shift may start between 5:00am - 10:00am",
    "SE": "Shift may start between 1:00pm - 6:00pm",
    "SN": "Shift may start between 6:00pm - 3:00am",
    "FX": "Shift may start between 7:00am - 7:00pm",
}


# --------------------------------------------------------------------------- #
# Hourly title families.
#
# placement tuple: (store_number, employment_type, shift_codes, min_pay,
#                   max_pay, positions_available, extras)
# `extras` is an optional dict: {"job_id": ..., "shift_time": ..., "min_age": bool}
# Body copy is a per-family template; slots are {banner} {store} {city} {state}.
# --------------------------------------------------------------------------- #
HOURLY_FAMILIES = [
    {
        "title": "Freight Handler",
        "area": "supply-chain-and-transportation",
        "category": "SC&T Operations",
        "hashtag": "#freighthandlerjobs",
        "summary": "Career opportunities in Freight Handling roles include Receiving, Unloading, "
                   "Processing, Orderfilling and Shipping.",
        "do": [
            "As a Freight Handler at {banner} #{store} in {city}, {state}, you will have a critical role "
            "in moving product through our supply chain network to the stores that serve our customers. "
            "Your role is critical in providing our customers with the product they expect at an everyday "
            "low price.",
            "You can expect the work to be very physically demanding with an extremely high focus on your "
            "safety and the safety of others. You will be lifting heavy cases in a climate-controlled and, "
            "at times, non-climate-controlled environment. The flow of freight is very fast-paced and "
            "productivity expectations are high.",
        ],
        "bring": [
            "Unload, sort and stage inbound freight using powered industrial equipment after certification.",
            "Scan and verify case counts against the trailer manifest and flag discrepancies to the area coach.",
            "Maintain a clean and safe work area, following all lockout/tagout and PPE requirements.",
            "Complies with company policies, procedures, and standards of ethics and integrity. Performs "
            "additional duties as assigned.",
        ],
        "placements": [
            ("9054", "Full time", "SN", 21.80, 25.30, 3, {"shift_time": "Shift may start between 6:00pm - 3:00am"}),
            ("9399", "Part time", "SE", 18.50, 22.00, 2, None),
            ("9046", "Full time", "WN", 20.90, 24.40, 4, {"shift_time": "Shift may start between 9:00pm - 1:30am"}),
            ("6038", "Full time", "WE", 19.75, 23.25, 2, {"shift_time": "Shift may start between 3:00pm - 7:30pm"}),
            ("9281", "Part time", "WD", 18.90, 22.40, 3, None),
            ("6014", "Part time", "SD", 19.40, 22.90, 5, None),
            ("7021", "Full time", "WN", 20.50, 24.00, 3, None),
        ],
    },
    {
        "title": "eCom Warehouse Worker",
        "area": "supply-chain-and-transportation",
        "category": "SC&T Operations",
        "hashtag": "#ecomwarehousejobs",
        "summary": "Pick, pack and ship the online orders that customers are waiting on, inside one of "
                   "our fulfillment buildings.",
        "do": [
            "As an eCom Warehouse Worker at {banner} #{store} in {city}, {state}, you pick customer orders "
            "from bins and totes, pack them to our quality standard, and hand them to the outbound dock so "
            "they ship the same night.",
            "Expect a fast, metrics-driven floor. You will stand and walk for most of your shift, lift up to "
            "50 pounds, and rotate across pick, pack and ship stations as volume moves.",
        ],
        "bring": [
            "Pick and pack customer orders to the published units-per-hour standard.",
            "Use a handheld scanner and the warehouse management system to confirm every unit.",
            "Report damaged product and inventory discrepancies before the order leaves the building.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("9046", "Part time", "SN", 21.35, 24.85, 2, {"job_id": "CP-9046-11274", "shift_time": "Shift may start between 6:00pm - 2:30am"}),
            ("9054", "Part time", "WN", 20.60, 24.10, 1, None),
            ("9281", "Part time", "SD,WN", 19.20, 22.70, 3, None),
            ("7133", "Full time", "WD", 18.80, 22.30, 4, None),
        ],
    },
    {
        "title": "Order Filler",
        "area": "supply-chain-and-transportation",
        "category": "SC&T Operations",
        "hashtag": "#orderfillerjobs",
        "summary": "Build store-ready pallets from the pick line and stage them for the outbound fleet.",
        "do": [
            "Order Fillers at {banner} #{store} in {city}, {state} select cases from the pick line, build "
            "stable pallets to the store's plan-o-gram sequence, wrap them, and stage them at the outbound "
            "door for the driver.",
            "You will use a rider pallet jack and a voice-directed pick system. Accuracy targets and case "
            "rates are published daily and reviewed with your coach each week.",
        ],
        "bring": [
            "Select cases accurately using a voice-directed picking headset.",
            "Build and wrap pallets that travel safely without shifting.",
            "Operate a rider pallet jack after completing on-site certification.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6014", "Full time", "WN,FX,SN", 19.10, 22.60, 4, None),
            ("7133", "Part time", "SE,FX", 18.40, 21.90, 2, None),
            ("6038", "Part time", "WD,FX", 20.10, 23.60, 3, None),
            ("9399", "Full time", "SN,FX", 19.85, 23.35, 2, None),
            ("7021", "Part time", "SD,FX", 19.30, 22.80, 2, None),
        ],
    },
    {
        "title": "Yard Driver-Off Property",
        "area": "supply-chain-and-transportation",
        "category": "Drivers",
        "hashtag": "#yarddriverjobs",
        "summary": "Move trailers between the yard, the dock doors and nearby off-property lots.",
        "do": [
            "Yard Drivers at {banner} #{store} in {city}, {state} shuttle trailers between dock doors, the "
            "on-site yard and nearby off-property parking so that inbound and outbound freight never waits "
            "on a door.",
            "You will spend the shift in a yard tractor, outdoors in all weather, coordinating over radio "
            "with the dock office and the guard shack.",
        ],
        "bring": [
            "Hold a valid Class A commercial driver's license with a clean motor vehicle record.",
            "Spot and pull trailers safely in tight yard conditions, day or night.",
            "Complete yard checks and record trailer locations in the yard management system.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6088", "Part time", "SE", 22.25, 25.75, 2, None),
            ("7133", "Part time", "WD", 23.10, 26.60, 1, None),
            ("6014", "Full time", "WN", 22.80, 26.30, 3, None),
            ("9399", "Part time", "FX,SN", 21.90, 25.40, 2, None),
        ],
    },
    {
        "title": "Class A CDL Truck Driver",
        "area": "supply-chain-and-transportation",
        "category": "Drivers",
        "hashtag": "#drivewithwalmart",
        "summary": "Run scheduled store deliveries out of a private fleet transportation office.",
        "do": [
            "Drivers based at {banner} #{store} in {city}, {state} run scheduled routes to stores and clubs "
            "in the surrounding region, unloading with the store team and returning with backhaul freight.",
            "Our private fleet runs newer equipment, publishes routes in advance and gets most drivers home "
            "regularly. Safety scorecards are reviewed with your transportation manager every month.",
        ],
        "bring": [
            "Hold a valid Class A CDL and meet all federal Department of Transportation requirements.",
            "At least 30 months of experience in the last 4 years driving a tractor trailer.",
            "No preventable accidents or serious traffic violations in the last three years.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6038", "Full time", "WD", 32.00, 41.00, 6, None),
            ("6014", "Full time", "SD,WN", 31.50, 40.50, 4, None),
            ("7133", "Full time", "WE", 30.75, 39.75, 5, None),
            ("6088", "Full time", "WN", 33.25, 42.25, 3, None),
        ],
    },
    {
        "title": "Asset Protection Associate - All DC/FC",
        "area": "supply-chain-and-transportation",
        "category": "Security and Asset Protection",
        "hashtag": "#dcassetprotectionjobs",
        "summary": "Protect people, product and property inside a distribution or fulfillment building.",
        "do": [
            "Asset Protection Associates at {banner} #{store} in {city}, {state} control access at the guard "
            "shack and associate entrances, audit trailer seals, and run the camera system that covers the "
            "dock and the yard.",
            "You will partner with operations leadership on safety walks, investigate shrink incidents, and "
            "write up findings for the asset protection manager.",
        ],
        "bring": [
            "Control access to the building and the yard, verifying credentials at every entry point.",
            "Audit inbound and outbound trailer seals against the manifest.",
            "Monitor camera systems and document incidents accurately and promptly.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("9046", "Part time", "WD,FX", 22.00, 25.50, 2, None),
            ("9054", "Part time", "SD,FX", 21.00, 24.50, 1, None),
            ("6088", "Full time", "WN", 22.50, 26.00, 2, None),
            ("7133", "Full time", "SN,FX", 23.00, 26.50, 1, None),
            ("6014", "Part time", "WE", 20.75, 24.25, 3, None),
        ],
    },
    {
        "title": "Facility Maintenance Technician",
        "area": "supply-chain-and-transportation",
        "category": "Engineering",
        "hashtag": "#facilitymaintenancejobs",
        "summary": "Keep conveyors, dock equipment and building systems running across the shift.",
        "do": [
            "Facility Maintenance Technicians at {banner} #{store} in {city}, {state} perform preventive "
            "maintenance and emergency repairs on conveyor systems, sortation equipment, dock levellers and "
            "building services.",
            "You will read schematics, troubleshoot electrical and mechanical faults, and close out work "
            "orders in the maintenance system before the end of your shift.",
        ],
        "bring": [
            "Two years of industrial maintenance experience or a completed technical program.",
            "Troubleshoot 480V three-phase systems, motor controls and pneumatics safely.",
            "Read and work from electrical, mechanical and pneumatic schematics.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("9046", "Full time", "WD,FX", 26.50, 34.00, 2, None),
            ("9281", "Full time", "WN,FX", 25.75, 33.25, 1, None),
            ("6038", "Full time", "SD", 27.00, 34.50, 2, None),
            ("7133", "Full time", "WE,FX", 26.00, 33.50, 3, None),
            ("6014", "Part time", "FX", 25.25, 32.75, 1, None),
            ("7021", "Full time", "WD,FX", 26.25, 33.75, 1, None),
        ],
    },
    {
        "title": "Automation Technician",
        "area": "supply-chain-and-transportation",
        "category": "Engineering",
        "hashtag": "#automationtechjobs",
        "summary": "Support the robotics and controls that run our automated storage and retrieval systems.",
        "do": [
            "Automation Technicians at {banner} #{store} in {city}, {state} maintain the robotics cells, "
            "programmable controllers and vision systems behind our automated storage and retrieval "
            "operation.",
            "You will run diagnostics from the controls HMI, replace failed drives and sensors, and escalate "
            "recurring faults to the controls engineering team with the data to back it up.",
        ],
        "bring": [
            "Experience maintaining PLC-controlled equipment, servo drives and industrial networks.",
            "Comfort working at height and in confined maintenance aisles under lockout/tagout.",
            "Track fault history and parts usage in the maintenance management system.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("9054", "Full time", "WN", 28.00, 36.00, 2, None),
            ("9399", "Full time", "SN", 27.50, 35.50, 1, None),
            ("6088", "Full time", "WD", 29.00, 37.00, 2, None),
        ],
    },
    {
        "title": "Aviation Line Service Technician",
        "area": "supply-chain-and-transportation",
        "category": "Aviation",
        "hashtag": "#aviationjobs",
        "summary": "Fuel, tow and service company aircraft on the ramp at a fleet operations base.",
        "do": [
            "Line Service Technicians supporting {banner} #{store} in {city}, {state} marshal, fuel, tow and "
            "de-ice company aircraft, and keep the ramp and hangar to airfield standard.",
            "You will work directly with flight crews and the maintenance team, following company and FAA "
            "ground handling procedures on every movement.",
        ],
        "bring": [
            "Ramp, fueling or ground handling experience at a fixed base operator or airline.",
            "Valid driver's license and the ability to obtain an airport security badge.",
            "Careful documentation of every fuel load and aircraft movement.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6014", "Full time", "WD", 24.00, 31.00, 1, None),
            ("7133", "Part time", "SD", 23.50, 30.50, 1, None),
            ("6088", "Part time", "WE", 22.75, 29.75, 2, None),
            ("6038", "Full time", "FX,SN", 24.50, 31.50, 1, None),
        ],
    },
    {
        "title": "Inventory Control Clerk",
        "area": "supply-chain-and-transportation",
        "category": "SC&T Operations",
        "hashtag": "#inventorycontroljobs",
        "summary": "Own cycle counts, research and the paperwork that keeps building inventory accurate.",
        "do": [
            "Inventory Control Clerks at {banner} #{store} in {city}, {state} run daily cycle counts, "
            "research variances between the system and the slot, and correct records so the building ships "
            "what the store ordered.",
            "Provides clerical and administrative support through generating and maintaining forms, reports "
            "and logs via computerized management software, and communicating with the operations team on "
            "open research.",
        ],
        "bring": [
            "Clerical duties (filing, keying, faxing), entering and extracting data from multiple systems.",
            "Use of computer applications required (email, spreadsheets, word processing, and Microsoft Office).",
            "The ability to be accurate and focus on attention to details will be critical.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("9281", "Part time", "WD,FX", 19.00, 22.50, 2, None),
            ("9399", "Part time", "WE,FX", 19.60, 23.10, 1, None),
            ("9046", "Full time", "SE,FX", 20.25, 23.75, 2, None),
        ],
    },
    # ----------------------------- Stores and Clubs ------------------------
    {
        "title": "Cashier & Front End Services",
        "area": "stores-and-clubs",
        "category": "Cashier and Front-End Services",
        "hashtag": "#frontendservicesjobs",
        "summary": "Greet members and customers at the front end, ring transactions and keep lines moving.",
        "do": [
            "At {banner} #{store} in {city}, {state} you are the last person a customer sees, so you set the "
            "tone for the whole trip. You ring up orders quickly and accurately, bag with care, and answer "
            "questions about returns, pickup and our app.",
            "You will rotate across registers, self checkout and the service desk depending on the hour, and "
            "you will be on your feet for most of the shift.",
        ],
        "bring": [
            "Ring transactions accurately and handle cash, cards and digital tenders.",
            "Support self checkout, resolving item and payment issues for customers.",
            "Process returns and exchanges at the service desk to policy.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2503", "Part time", "WD,SD", 15.00, 24.00, 5, None),
            ("2610", "Full time", "WD,WE,SD", 15.00, 24.00, 3, None),
            ("3512", "Part time", "SE,SN", 15.00, 23.00, 4, None),
            ("8763", "Part time", "SE,SN", 16.00, 25.00, 2, None),
            ("2110", "Full time", "WD,WE", 15.50, 26.00, 4, None),
            ("5382", "Part time", "WE,SE", 17.00, 28.00, 3, None),
            ("3593", "Part time", "WE,SN", 15.00, 23.50, 4, None),
            ("2075", "Part time", "WE,SE", 15.50, 25.50, 2, None),
            ("3826", "Part time", "WE,SE", 15.00, 24.50, 2, None),
        ],
    },
    {
        "title": "Cosmetics Cashier",
        "area": "stores-and-clubs",
        "category": "Cashier and Front-End Services",
        "hashtag": "#cosmeticscashierjobs",
        "summary": "Run the beauty counter register and keep the cosmetics department shoppable.",
        "do": [
            "The cosmetics counter at {banner} #{store} in {city}, {state} has its own register and its own "
            "regulars. You ring transactions there, help customers find shades and brands, and keep the "
            "planogram faced and stocked.",
            "You will also handle the department's security cases and coordinate restock with the general "
            "merchandise team.",
        ],
        "bring": [
            "Ring transactions at a departmental register and reconcile the till at shift end.",
            "Keep the beauty planogram faced, stocked and free of expired product.",
            "Open locked cases for customers and follow high-theft merchandise procedures.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2503", "Part time", "WD,WE", 15.00, 24.00, 1, None),
            ("3520", "Part time", "SD,SE", 15.00, 24.00, 2, None),
            ("2163", "Part time", "WE,SE", 15.00, 25.00, 1, None),
        ],
    },
    {
        "title": "Member Services Associate",
        "area": "stores-and-clubs",
        "category": "Cashier and Front-End Services",
        "hashtag": "#memberservicesjobs",
        "summary": "Sign up new members, renew memberships and solve problems at the member services desk.",
        "do": [
            "At {banner} #{store} in {city}, {state} you own the member services desk: new sign-ups, "
            "renewals, upgrades, returns and the occasional tough conversation.",
            "You will explain plan tiers and instant savings honestly, resolve billing questions, and hand "
            "off anything you cannot fix to the club lead with the full picture.",
        ],
        "bring": [
            "Enroll, renew and upgrade memberships accurately in the membership system.",
            "Process returns and refunds within club policy.",
            "Explain plan benefits clearly without overselling.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("8259", "Full time", "WD,SD", 18.00, 26.00, 2, None),
            ("6318", "Part time", "WE,SE", 16.00, 24.00, 3, None),
            ("8763", "Full time", "WD,WE", 16.00, 24.00, 1, None),
            ("4744", "Part time", "WE,SE", 16.50, 24.50, 3, None),
            ("8155", "Full time", "WD,SD", 17.00, 25.00, 2, None),
        ],
    },
    {
        "title": "Food & Grocery Associate",
        "area": "stores-and-clubs",
        "category": "Food and Grocery",
        "hashtag": "#foodandgroceryjobs",
        "summary": "Stock, rotate and merchandise the grocery aisles, coolers and freezers.",
        "do": [
            "Food & Grocery Associates at {banner} #{store} in {city}, {state} unload the grocery truck, "
            "stock dry, chilled and frozen departments, rotate dated product, and zone the aisles so the "
            "store is shoppable at open.",
            "You will handle food safety checks on your section and pull anything past code before it "
            "reaches a customer.",
        ],
        "bring": [
            "Stock and rotate product following first-in, first-out standards.",
            "Complete temperature and date checks for chilled and frozen sections.",
            "Operate a manual and electric pallet jack after certification.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2110", "Full time", "WD,WE", 15.50, 26.00, 3, None),
            ("2050", "Part time", "WE,SE", 17.50, 28.00, 2, None),
            ("471", "Full time", "WD,SD", 15.00, 25.00, 4, None),
            ("1236", "Part time", "WN,SN", 16.00, 26.00, 2, {"job_id": "CP-1236-10741"}),
            ("5388", "Full time", "WN", 16.50, 27.00, 2, None),
            ("5133", "Full time", "WE,SN", 16.00, 26.50, 2, None),
        ],
    },
    {
        "title": "Freezer/Cooler Associate",
        "area": "stores-and-clubs",
        "category": "Food and Grocery",
        "hashtag": "#freezercoolerjobs",
        "summary": "Work the club's freezer and cooler boxes, stocking bulk frozen and chilled product.",
        "do": [
            "At {banner} #{store} in {city}, {state} you spend most of the shift inside the freezer and "
            "cooler boxes, breaking down pallets of bulk frozen and chilled product and building the club "
            "floor displays.",
            "Cold weather gear is provided. You will follow scheduled warm-up breaks and log box "
            "temperatures every rotation.",
        ],
        "bring": [
            "Work extended periods in temperatures as low as minus ten degrees Fahrenheit.",
            "Break down pallets and build club floor displays to the merchandising plan.",
            "Record freezer and cooler temperatures on the posted schedule.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6608", "Full time", "WD,WN", 19.00, 27.00, 1, None),
            ("4750", "Part time", "SN,WN", 17.50, 25.50, 2, None),
            ("8253", "Full time", "WN,SN", 17.00, 25.00, 1, None),
            ("8155", "Part time", "WN,SN", 17.50, 25.50, 2, None),
        ],
    },
    {
        "title": "General Merchandise Associate",
        "area": "stores-and-clubs",
        "category": "General Merchandise, Stocking, and Unloading",
        "hashtag": "#generalmerchandisejobs",
        "summary": "Unload, sort and stock general merchandise across the sales floor.",
        "do": [
            "General Merchandise Associates at {banner} #{store} in {city}, {state} unload trailers, sort "
            "freight to department, stock shelves and pull back the overhead so the floor stays full.",
            "You will work modular resets, price changes and seasonal transitions alongside the department "
            "team lead.",
        ],
        "bring": [
            "Unload and sort freight accurately to department.",
            "Stock, zone and face assigned departments to company standard.",
            "Execute modular resets and seasonal transitions on schedule.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2050", "Part time", "WN,SN", 17.50, 28.00, 3, None),
            ("3387", "Part time", "WD,SD", 15.00, 25.00, 2, None),
            ("1179", "Full time", "WE,SE,WN", 15.00, 25.00, 4, None),
            ("954", "Part time", "WD,WE", 15.00, 24.00, 2, None),
            ("5133", "Part time", "SD,SE", 15.50, 25.50, 3, None),
        ],
    },
    {
        "title": "Stocking Associate",
        "area": "stores-and-clubs",
        "category": "General Merchandise, Stocking, and Unloading",
        "hashtag": "#stockingassociatejobs",
        "summary": "Work the overnight stocking team, filling the store before the doors open.",
        "do": [
            "Stocking Associates at {banner} #{store} in {city}, {state} work the truck overnight: unload, "
            "sort to aisle, stock, break down cardboard and zone the floor so the store looks new at open.",
            "The pace is set by the truck. You will move steadily for the whole shift with a small team and "
            "a clear finish line.",
        ],
        "bring": [
            "Stock assigned aisles completely and accurately before the store opens.",
            "Break down and bale cardboard, keeping aisles clear and safe.",
            "Use a manual pallet jack and rolltainers safely in tight aisles.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("1230", "Full time", "WN", 15.50, 24.50, 3, None),
            ("2163", "Part time", "SN,WN", 16.50, 26.50, 2, None),
            ("2075", "Full time", "WD,SD", 16.00, 25.00, 3, None),
            ("3593", "Part time", "WN", 15.00, 24.00, 2, None),
        ],
    },
    {
        "title": "Merchandising and Stocking Associate",
        "area": "stores-and-clubs",
        "category": "General Merchandise, Stocking, and Unloading",
        "hashtag": "#merchandisingjobs",
        "summary": "Build club pallets and keep the sales floor merchandised to plan.",
        "do": [
            "At {banner} #{store} in {city}, {state} you stock bulk club pallets, build feature displays at "
            "the action alley, and keep signage and pricing accurate across your zone.",
            "You will use an electric pallet jack and order picker after certification, and you will work "
            "with the merchandising lead on weekly display changes.",
        ],
        "bring": [
            "Stock club pallets and build feature displays to the merchandising plan.",
            "Verify signage and pricing against the weekly plan every shift.",
            "Operate an electric pallet jack and order picker after certification.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("4750", "Part time", "SN,WN", 17.00, 19.50, 3, None),
            ("6318", "Part time", "SN,SD", 21.00, 24.50, 2, None),
            ("6636", "Full time", "SN,WN", 18.00, 19.75, 4, None),
            ("8253", "Part time", "SN,WE", 17.50, 19.25, 2, None),
            ("6216", "Part time", "WN,WD", 18.50, 19.90, 3, None),
            ("8763", "Part time", "SN,SE", 16.50, 18.75, 1, None),
        ],
    },
    {
        "title": "Online Order Filling Team Associate",
        "area": "stores-and-clubs",
        "category": "Digital Pickup and Delivery",
        "hashtag": "#onlineorderfillingjobs",
        "summary": "Shop, stage and hand off customer pickup and delivery orders.",
        "do": [
            "Online Order Filling Team Associates at {banner} #{store} in {city}, {state} shop customer "
            "orders from the sales floor with a cart and a handheld, choose the freshest substitutions when "
            "an item is out, and stage completed orders in the pickup coolers.",
            "You will also load orders into customer vehicles at the pickup canopy and hand off to delivery "
            "drivers on schedule.",
        ],
        "bring": [
            "Pick customer orders accurately against the handheld pick list.",
            "Choose quality substitutions and communicate them to the customer.",
            "Stage orders at the correct temperature and load them at the pickup canopy.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("1399", "Part time", "WD,WE,SD", 14.50, 27.50, 3, None),
            ("144", "Full time", "WD,SD", 15.50, 26.00, 2, None),
            ("5991", "Part time", "WE,SE", 17.50, 28.00, 4, None),
            ("5260", "Full time", "WD,WE,SE", 15.00, 28.00, 2, None),
            ("5388", "Part time", "WE,SE", 16.00, 27.00, 2, None),
            ("2075", "Full time", "WD,WE", 15.50, 26.50, 3, None),
            ("3826", "Full time", "WD,SD", 15.00, 26.00, 2, None),
            ("3593", "Full time", "WD,SE", 14.50, 25.00, 4, None),
        ],
    },
    {
        "title": "Online Order Filling Team Supervisor",
        "area": "stores-and-clubs",
        "category": "Digital Pickup and Delivery",
        "hashtag": "#digitalpickupleadjobs",
        "summary": "Lead the pickup and delivery team through the day's order volume.",
        "do": [
            "The Online Order Filling Team Supervisor at {banner} #{store} in {city}, {state} runs the "
            "digital team for the shift: assigns pickers, watches the order clock, and steps in wherever "
            "the queue is tightest.",
            "You will coach on pick quality and substitution decisions, handle escalated customer issues at "
            "the canopy, and report on-time performance to the store lead each day.",
        ],
        "bring": [
            "Assign and balance pick work across the team through peak windows.",
            "Coach associates on pick accuracy, substitutions and customer handoff.",
            "Resolve escalated pickup and delivery issues at the canopy.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2073", "Full time", "WD,SD", 20.00, 33.00, 2, None),
            ("1179", "Full time", "WD,WE", 19.50, 32.00, 1, None),
            ("5439", "Part time", "WE,SE", 19.00, 31.50, 2, None),
        ],
    },
    {
        "title": "Cafe Associate",
        "area": "stores-and-clubs",
        "category": "Cafe",
        "hashtag": "#cafeassociatejobs",
        "summary": "Run the club cafe: prep, grill, serve and keep the counter to food safety standard.",
        "do": [
            "Cafe Associates at {banner} #{store} in {city}, {state} take orders, prep and cook to the "
            "posted recipe cards, and keep the counter, the drink station and the seating area clean "
            "through the rush.",
            "You will run opening or closing food safety checklists and log temperatures on every batch.",
        ],
        "bring": [
            "Prepare food to recipe and hold it at safe temperatures.",
            "Complete opening, mid-shift and closing food safety logs.",
            "Keep the counter, equipment and seating area clean and stocked.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6608", "Part time", "WD,WE", 17.00, 24.00, 2, None),
            ("8259", "Part time", "WD,SD", 16.00, 23.00, 1, None),
            ("6318", "Part time", "SD,SE,FX", 15.50, 22.50, 3, None),
            ("6636", "Part time", "WD,SD", 16.00, 23.00, 2, None),
            ("4744", "Full time", "WD,SD", 16.50, 23.50, 2, None),
        ],
    },
    {
        "title": "Team Lead",
        "area": "stores-and-clubs",
        "category": "Retail Management",
        "hashtag": "#teamleadjobs",
        "summary": "Lead a department team, own its standards and develop the associates on it.",
        "do": [
            "Team Leads at {banner} #{store} in {city}, {state} run a department end to end: staffing the "
            "shift, setting priorities at the huddle, working the floor alongside the team and owning the "
            "department's sales and in-stock results.",
            "You will coach associates day to day, handle customer escalations, and partner with the coach "
            "on scheduling and development plans.",
        ],
        "bring": [
            "Plan and assign daily work for a department team.",
            "Coach associates on standards and follow through on development plans.",
            "Own department in-stock, shrink and customer experience results.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("144", "Full time", "WD,WE", 19.00, 32.00, 1, None),
            ("2073", "Full time", "WD,WE", 20.00, 33.00, 1, None),
            ("4137", "Full time", "WD,SD", 21.00, 34.00, 2, None),
            ("2610", "Full time", "WE,SE", 18.00, 30.00, 1, None),
        ],
    },
    {
        "title": "Coach",
        "area": "stores-and-clubs",
        "category": "Retail Management",
        "hashtag": "#storeleadershipjobs",
        "summary": "Lead several departments and the team leads who run them.",
        "do": [
            "Coaches at {banner} #{store} in {city}, {state} lead a group of departments and the team leads "
            "inside them, owning results for sales, availability, shrink and associate engagement across "
            "that area of the building.",
            "You will spend the day on the floor, remove barriers for your leads, and hold the standard "
            "when the store is busiest.",
        ],
        "bring": [
            "Lead team leads and associates across multiple departments.",
            "Own area results for sales, in-stock, shrink and engagement.",
            "Build talent through structured coaching and succession planning.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("1230", "Full time", "WD,SD", 23.00, 38.00, 1, None),
            ("2163", "Full time", "WE,SE", 24.00, 39.00, 1, None),
        ],
    },
    {
        "title": "Fuel Station Associate",
        "area": "stores-and-clubs",
        "category": "Fuel Station",
        "hashtag": "#fuelstationjobs",
        "summary": "Run the club fuel station: assist members, check equipment and keep the site compliant.",
        "do": [
            "Fuel Station Associates at {banner} #{store} in {city}, {state} greet members at the pumps, "
            "help with payment issues, complete daily equipment and environmental checks, and keep the "
            "island clean and stocked.",
            "You will work outdoors in all weather and follow strict fuel handling and spill response "
            "procedures.",
        ],
        "bring": [
            "Complete daily fuel equipment, tank and environmental compliance checks.",
            "Assist members at the pump and resolve payment issues.",
            "Follow fuel handling, spill response and emergency shutdown procedures.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6636", "Part time", "WD,SD,FX", 16.50, 23.50, 2, None),
            ("8253", "Part time", "WE,SE", 15.50, 22.50, 1, None),
            ("6216", "Part time", "SN,WN", 17.00, 24.00, 2, None),
            ("4750", "Full time", "WD,WN", 16.00, 23.00, 1, None),
        ],
    },
    {
        "title": "Auto Care Center Technician",
        "area": "stores-and-clubs",
        "category": "Auto Care Center",
        "hashtag": "#autocarecenterjobs",
        "summary": "Perform tire, battery and light maintenance service in the Auto Care Center.",
        "do": [
            "Auto Care Center Technicians at {banner} #{store} in {city}, {state} mount and balance tires, "
            "install batteries, change oil and complete light maintenance services while the customer "
            "shops.",
            "You will inspect vehicles honestly, document every service performed, and keep the bay and "
            "equipment to safety standard.",
        ],
        "bring": [
            "Mount, balance and repair tires and install batteries safely.",
            "Complete oil changes and light maintenance to manufacturer specification.",
            "Document every inspection and service accurately in the shop system.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("954", "Full time", "WD,SD", 17.00, 30.00, 3, None),
            ("1230", "Full time", "WD,WE", 17.00, 30.00, 5, None),
            ("471", "Part time", "WE,SE", 16.50, 29.00, 2, None),
            ("1179", "Full time", "WD,SD", 17.50, 30.50, 1, None),
            ("5133", "Full time", "WD,SD", 17.50, 30.50, 2, None),
        ],
    },
    {
        "title": "Tire & Battery Technician",
        "area": "stores-and-clubs",
        "category": "Auto Services",
        "hashtag": "#tireandbatteryjobs",
        "summary": "Service member vehicles in the club tire and battery center.",
        "do": [
            "Tire & Battery Technicians at {banner} #{store} in {city}, {state} install and rotate tires, "
            "test and replace batteries, and complete the free member services the club is known for.",
            "You will work the service write-up desk as well as the bay, so clear explanations matter as "
            "much as clean work.",
        ],
        "bring": [
            "Install, rotate and repair tires to torque and safety specification.",
            "Test and replace batteries and charging system components.",
            "Write up member services clearly and set accurate expectations on timing.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6608", "Full time", "WD,WE", 19.00, 27.00, 2, None),
            ("4750", "Part time", "SD,SE", 17.50, 25.50, 1, None),
            ("6216", "Full time", "WD,SD", 18.50, 26.50, 2, None),
            ("8259", "Part time", "WE,SN", 17.00, 25.00, 1, None),
        ],
    },
    {
        "title": "Maintenance Technician",
        "area": "stores-and-clubs",
        "category": "Maintenance",
        "hashtag": "#storemaintenancejobs",
        "summary": "Keep store equipment, refrigeration and building systems running.",
        "do": [
            "Maintenance Technicians at {banner} #{store} in {city}, {state} respond to equipment calls "
            "across the building: refrigeration alarms, doors, carts, lighting, HVAC and the compactor.",
            "You will complete scheduled preventive maintenance, escalate refrigerant work to the "
            "certified contractor, and close every work order with what you actually did.",
        ],
        "bring": [
            "Diagnose and repair store equipment, lighting and building systems.",
            "Complete scheduled preventive maintenance on time.",
            "Follow lockout/tagout and electrical safety procedures without exception.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2073", "Full time", "WN,SN,FX", 20.00, 30.00, 1, None),
            ("1399", "Part time", "WE,SE,FX", 18.00, 28.00, 2, None),
            ("5439", "Full time", "WD,WE,FX", 19.00, 29.00, 1, None),
            ("3512", "Full time", "WD,SD", 17.00, 26.00, 2, None),
        ],
    },
    {
        "title": "Asset Protection Associate",
        "area": "stores-and-clubs",
        "category": "Security and Asset Protection",
        "hashtag": "#assetprotectionjobs",
        "summary": "Reduce shrink and keep associates and customers safe inside the store.",
        "do": [
            "Asset Protection Associates at {banner} #{store} in {city}, {state} work the floor and the "
            "camera room, deter theft, respond to alarms, and partner with store leadership on safety "
            "walks and incident follow-up.",
            "You will document every incident to policy and work with local law enforcement when the "
            "asset protection manager asks you to.",
        ],
        "bring": [
            "Deter and document theft following company approach and apprehension policy.",
            "Monitor camera and EAS systems and respond to alarms.",
            "Complete safety walks and incident reports accurately.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("5991", "Full time", "WD,WE,SD", 17.00, 30.00, 2, None),
            ("3387", "Part time", "SE,SN", 16.00, 28.00, 1, None),
            ("5382", "Full time", "WD,SD", 19.00, 32.00, 1, None),
            ("5388", "Full time", "WD,SD", 18.00, 30.00, 2, None),
        ],
    },
    {
        "title": "Asset Protection Customer Specialist",
        "area": "stores-and-clubs",
        "category": "Security and Asset Protection",
        "hashtag": "#apcustomerspecialistjobs",
        "summary": "Greet at the entrance, verify receipts and keep the front of the store secure.",
        "do": [
            "Asset Protection Customer Specialists at {banner} #{store} in {city}, {state} work the "
            "entrance: greeting every customer, verifying receipts at the door, and watching the front end "
            "for problems before they grow.",
            "You will support the asset protection team with documentation and keep the entry area clean, "
            "carted and welcoming.",
        ],
        "bring": [
            "Greet customers at the entrance and verify receipts at the exit.",
            "Watch front-end activity and escalate concerns to asset protection.",
            "Keep the entry area stocked with carts and free of hazards.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2503", "Full time", "WD,WE", 16.00, 26.00, 1, None),
            ("5260", "Part time", "WE,SE", 17.00, 28.00, 2, None),
        ],
    },
    # ------------------------------- Healthcare ----------------------------
    {
        "title": "Pharmacy Technician",
        "area": "healthcare",
        "category": "Pharmacy Services",
        "hashtag": "#pharmacytechjobs",
        "summary": "Support the pharmacist with intake, data entry, filling and patient pickup.",
        "do": [
            "Pharmacy Technicians at {banner} #{store} in {city}, {state} take in prescriptions, enter and "
            "verify patient and insurance information, count and label under the pharmacist's supervision, "
            "and hand off at the pickup window.",
            "You will work third-party rejections, call prescribers for clarifications, and keep the "
            "workflow moving so patients are not waiting on paperwork.",
        ],
        "bring": [
            "Enter prescription and insurance information accurately into the pharmacy system.",
            "Fill and label prescriptions under the direct supervision of the pharmacist.",
            "Resolve third-party rejections and coordinate with prescriber offices.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("5260", "Full time", "WD,SD", 18.00, 30.00, 2, None),
            ("4137", "Part time", "WE,SE", 19.50, 32.00, 1, None),
            ("2110", "Full time", "WD,WE", 18.50, 30.50, 1, None),
            ("2050", "Part time", "SD,SE", 20.00, 33.00, 2, None),
            ("3826", "Full time", "WD,WE", 18.50, 31.00, 3, None),
        ],
    },
    {
        "title": "Certified Pharmacy Technician",
        "area": "healthcare",
        "category": "Pharmacy Services",
        "hashtag": "#certifiedpharmacytechjobs",
        "summary": "Work at the top of your certification supporting immunizations and clinical services.",
        "do": [
            "Certified Pharmacy Technicians at {banner} #{store} in {city}, {state} do everything a "
            "technician does, plus the work that certification unlocks: immunization support, medication "
            "therapy outreach and inventory ownership for controlled substances.",
            "You will mentor uncertified technicians on workflow and accuracy, and cover the pharmacist's "
            "administrative queue during clinical blocks.",
        ],
        "bring": [
            "Hold and maintain a current state pharmacy technician certification.",
            "Support immunization clinics and medication therapy outreach.",
            "Own perpetual inventory counts for controlled substances.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("3520", "Full time", "WD,WE", 21.00, 34.00, 1, None),
            ("1236", "Part time", "WE,SD", 19.00, 31.00, 2, None),
        ],
    },
    {
        "title": "Optician",
        "area": "healthcare",
        "category": "Optical Services",
        "hashtag": "#opticianjobs",
        "summary": "Fit, adjust and dispense eyewear in the Vision Center.",
        "do": [
            "Opticians at {banner} #{store} in {city}, {state} interpret prescriptions, take measurements, "
            "recommend lens options honestly, and fit and adjust finished eyewear so it is comfortable on "
            "day one.",
            "You will also run the lab bench work the store handles in house, manage the frame board, and "
            "coordinate with the independent optometrist's office next door.",
        ],
        "bring": [
            "Interpret ophthalmic prescriptions and take accurate fitting measurements.",
            "Recommend frames and lens treatments suited to the prescription and budget.",
            "Adjust, repair and dispense finished eyewear to specification.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2073", "Full time", "WD,SD", 21.50, 34.50, 1, None),
            ("5382", "Part time", "WE,SE", 23.00, 36.00, 1, None),
            ("1236", "Full time", "WD,WE", 21.00, 34.00, 1, None),
            ("5991", "Full time", "WD,WE,SD", 22.00, 35.00, 2, None),
            ("5133", "Full time", "WD,SD", 21.50, 34.50, 1, None),
            ("3826", "Part time", "WE,SE", 22.50, 35.50, 1, None),
        ],
    },
    {
        "title": "Vision Center Associate",
        "area": "healthcare",
        "category": "Optical Services",
        "hashtag": "#visioncenterjobs",
        "summary": "Greet vision center customers, schedule exams and support the optician.",
        "do": [
            "Vision Center Associates at {banner} #{store} in {city}, {state} welcome customers, schedule "
            "exams with the on-site optometrist, verify vision benefits and support the optician with "
            "dispensing and repairs.",
            "You will keep the frame board merchandised and the exam schedule full without overbooking.",
        ],
        "bring": [
            "Schedule exams and verify vision insurance benefits.",
            "Support dispensing, adjustments and simple frame repairs.",
            "Keep the frame board merchandised, priced and clean.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("471", "Part time", "WD,SD", 16.00, 26.00, 2, None),
            ("5439", "Part time", "WE,SE", 17.00, 27.00, 1, None),
        ],
    },
    {
        "title": "Health & Wellness Operations Associate",
        "area": "healthcare",
        "category": "Health and Wellness Operations",
        "hashtag": "#healthandwellnessjobs",
        "summary": "Keep the health and wellness area stocked, compliant and ready for patients.",
        "do": [
            "Health & Wellness Operations Associates at {banner} #{store} in {city}, {state} own the "
            "operational side of the department: over-the-counter stocking, expiration audits, compliance "
            "logs and the patient waiting area.",
            "You will support screening events, keep the private consultation room ready, and route "
            "patient questions to the pharmacist correctly.",
        ],
        "bring": [
            "Complete over-the-counter stocking and expiration audits on schedule.",
            "Maintain compliance logs and the private consultation area.",
            "Support screening and immunization events with setup and intake.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("2050", "Full time", "WD,WE", 18.00, 29.00, 1, None),
            ("3387", "Part time", "SD,SE", 17.00, 28.00, 2, None),
            ("3512", "Part time", "WD,SD", 17.50, 28.50, 1, None),
            ("1399", "Part time", "WE,SN", 18.50, 29.50, 2, None),
        ],
    },
    {
        "title": "Certified Medical Assistant",
        "area": "healthcare",
        "category": "Clinical Care",
        "hashtag": "#clinicalcarejobs",
        "summary": "Room patients, take vitals and support the clinician in a community care setting.",
        "do": [
            "Certified Medical Assistants supporting {banner} #{store} in {city}, {state} greet and room "
            "patients, take vitals and history, prepare the room, and assist the clinician during the "
            "visit.",
            "You will document in the electronic health record, handle specimen collection and labelling, "
            "and close out visit instructions with the patient before they leave.",
        ],
        "bring": [
            "Hold a current medical assistant certification and BLS card.",
            "Take and document vitals, history and medication reconciliation accurately.",
            "Collect and label specimens following chain-of-custody procedures.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("1236", "Full time", "WD,WE", 19.00, 30.00, 1, None),
            ("3520", "Part time", "WD,SD", 22.00, 34.00, 2, None),
            ("2610", "Part time", "WE,SE", 19.50, 30.50, 1, None),
            ("954", "Part time", "WD,SD", 18.00, 29.00, 2, None),
        ],
    },
    # ------------------------------- Students (hourly) ---------------------
    {
        "title": "Retail Operations Intern",
        "area": "students",
        "category": "Internship",
        "hashtag": "#walmartinternships",
        "summary": "A paid store internship rotating through front end, digital and merchandising.",
        "do": [
            "Retail Operations Interns at {banner} #{store} in {city}, {state} spend the term rotating "
            "through the front end, the digital pickup team and a merchandising department, with a store "
            "leader as your mentor.",
            "You will finish the program by presenting one operational improvement you scoped, tested and "
            "measured inside the building.",
        ],
        "bring": [
            "Currently enrolled in an associate or bachelor's degree program.",
            "Availability for a full internship term including some weekend coverage.",
            "Willingness to work the floor in every rotation, not just observe.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("144", "Intern", "WD,FX", 16.00, 20.00, 1, None),
            ("2073", "Intern", "WD,FX", 16.50, 20.50, 1, None),
            ("4137", "Intern", "WE,FX", 17.00, 21.00, 1, None),
            ("2503", "Intern", "WD,SD", 15.00, 19.00, 1, None),
            ("2050", "Intern", "WD,FX", 16.25, 20.25, 1, None),
            ("1179", "Intern", "WE,FX", 16.75, 20.75, 1, None),
            ("3387", "Intern", "WD,SD", 15.50, 19.50, 1, None),
        ],
    },
    {
        "title": "Club Operations Intern",
        "area": "students",
        "category": "Internship",
        "hashtag": "#samsclubinternships",
        "summary": "A paid club internship focused on membership growth and fresh operations.",
        "do": [
            "Club Operations Interns at {banner} #{store} in {city}, {state} work with the club manager on "
            "membership growth, fresh area operations and the weekly merchandising plan.",
            "You will own one measurable project for the term and present the results to the club "
            "leadership team.",
        ],
        "bring": [
            "Currently enrolled in an associate or bachelor's degree program.",
            "Interest in retail operations, membership models or fresh category management.",
            "Availability for a full internship term including some weekend coverage.",
            "Complies with company policies, procedures, and standards of ethics and integrity.",
        ],
        "placements": [
            ("6608", "Intern", "WD,FX", 18.00, 22.00, 1, None),
            ("6318", "Intern", "WE,FX", 16.50, 20.50, 1, None),
            ("8259", "Intern", "WD,SD", 17.25, 21.25, 1, None),
            ("6216", "Intern", "WE,FX", 17.75, 21.75, 1, None),
            ("4744", "Intern", "WD,FX", 17.00, 21.00, 1, None),
            ("8155", "Intern", "WE,FX", 17.50, 21.50, 1, None),
        ],
    },
]

# --------------------------------------------------------------------------- #
# Salaried title families.
#
# placement tuple: (store_number, employment_type, min_pay, max_pay,
#                   worker_type, qual_slots, extras)
# `qual_slots` = (degree_field, option1_years, option2_years, preferred_slot)
# `extras` is an optional dict: {"job_id": ..., "qual_clause": ...}
# Minimum-qualification text is built from the family's template with those
# slots, so every posting's Option 1 / Option 2 text is unique. A `qual_clause`
# is appended to both options ("..., including <clause>.") so that posting's
# qualification text is specific to this mirror.
#
# Pinned job_ids are synthetic: none of them is a requisition ID that exists on
# careers.walmart.com.
# --------------------------------------------------------------------------- #
SALARIED_FAMILIES = [
    {
        "title": "Staff, Software Engineer - Backend / ML",
        "area": "technology",
        "category": "Software Engineering and Architecture",
        "shifts": "WD,SD",
        "summary": "Set the technical direction for backend microservices and ML-serving "
                   "infrastructure at retail scale.",
        "do": [
            "As a Staff Software Engineer at {location_name} in {city}, {state}, you'll be a technical "
            "leader who defines the direction for and evolves the backend microservices, data pipelines, "
            "and ML-serving infrastructure that power search at massive scale. You'll lead a team of six "
            "to ten engineers, set the technical vision for critical systems, and drive the quality bar "
            "across the team.",
            "We're in an active phase of platform modernization - redesigning and refactoring core "
            "systems. If you want to build, not just maintain, this is the right time to join.",
        ],
        "about_team": "The eCommerce Search engineering team owns the end-to-end technology stack that "
                      "powers product search and discovery across Walmart's global eCommerce channels, "
                      "backed by microservices, large-scale data and feature pipelines, search engines, "
                      "and ML model serving infrastructure.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "software engineering or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in software engineering or related area.",
        "preferred": "Master's degree in {degree_field} and {yp} years' experience in software "
                     "engineering or related area. We value candidates with a background in creating "
                     "inclusive digital experiences and knowledge of Web Content Accessibility "
                     "Guidelines (WCAG) 2.2 AA standards.",
        "placements": [
            ("11807", "Full time", 143000, 286000, "Regular/Permanent",
             ("computer science, computer engineering, computer information systems, software engineering, or related area", 5, 7, 2),
             {"job_id": "R-2468347",
              "qual_clause": "including experience operating search or ML-serving systems in production"}),
            ("10101", "Full time", 132000, 264000, "Regular/Permanent",
             ("computer science, computer engineering, or related area", 5, 8, 3), None),
            ("12200", "Full time", 128000, 246000, "Regular/Permanent",
             ("computer science, electrical engineering, or related area", 6, 9, 3), None),
        ],
    },
    {
        "title": "Senior Software Engineer",
        "area": "technology",
        "category": "Software Engineering and Architecture",
        "shifts": "WD",
        "summary": "Design, build and operate the services behind checkout, fulfillment and search.",
        "do": [
            "Senior Software Engineers at {location_name} in {city}, {state} own services end to end: "
            "design, implementation, deployment and on-call. You will partner with product and data "
            "science to turn ambiguous problems into systems that hold up at Walmart's traffic.",
            "You will review designs and code across the team, mentor engineers earlier in their careers, "
            "and keep an eye on cost, latency and reliability as much as on features.",
        ],
        "about_team": "This team builds and runs the platform services that thousands of engineers and "
                      "millions of customers depend on every day.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "software engineering or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in software engineering or related area.",
        "preferred": "Master's degree in {degree_field} and {yp} years' experience building distributed "
                     "systems in production.",
        "placements": [
            ("11003", "Full time", 110000, 220000, "Regular/Permanent",
             ("computer science, computer information systems, or related area", 4, 7, 1),
             {"qual_clause": "including experience building high-volume checkout or payments services"}),
            ("11807", "Full time", 117000, 234000, "Regular/Permanent",
             ("computer engineering, software engineering, or related area", 4, 7, 2), None),
            ("10101", "Full time", 96000, 192000, "Regular/Permanent",
             ("information systems, computer science, or related area", 2, 4, 1), None),
            ("12200", "Full time", 105000, 195000, "Regular/Permanent",
             ("embedded systems, computer engineering, or related area", 3, 6, 2), None),
        ],
    },
    {
        "title": "Software Engineer III",
        "area": "technology",
        "category": "Software Engineering and Architecture",
        "shifts": "WD",
        "summary": "Build features across the smart TV platform and its content services.",
        "do": [
            "Software Engineers at {location_name} in {city}, {state} build and ship features across the "
            "platform, from the on-device experience to the services behind it.",
            "You will write production code every week, take part in design reviews, and work with QA and "
            "product on release readiness.",
        ],
        "about_team": "The platform engineering group builds the software that runs on millions of "
                      "connected devices in customers' living rooms.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "software engineering or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in software engineering or related area.",
        "preferred": "Experience with embedded platforms and {yp} years' experience shipping consumer "
                     "software at scale.",
        "placements": [
            ("12200", "Full time", 90000, 180000, "Regular/Permanent",
             ("computer science or related area", 2, 4, 3), {"job_id": "R-2417063"}),
        ],
    },
    {
        "title": "Senior Manager, Product Management",
        "area": "technology",
        "category": "Product Management",
        "shifts": "WD",
        "summary": "Own a product area end to end, from strategy through launch and iteration.",
        "do": [
            "Senior Managers of Product Management at {location_name} in {city}, {state} own a product "
            "area: the strategy, the roadmap, the trade-offs and the results.",
            "You will work daily with engineering, design and data science, and you will be the person "
            "who says no often enough that the yes means something.",
        ],
        "about_team": "Product management at Walmart sits close to the customer and close to the code.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "product management or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in product management or related area.",
        "preferred": "Master's degree in business administration and {yp} years' experience leading "
                     "product teams.",
        "placements": [
            ("10101", "Full time", 110000, 220000, "Regular/Permanent",
             ("business, analytics, engineering, or related area", 5, 7, 2), {"job_id": "R-2418512"}),
            ("11807", "Full time", 132000, 264000, "Regular/Permanent",
             ("computer science, business, or related area", 6, 9, 3), None),
            ("11003", "Full time", 90000, 180000, "Regular/Permanent",
             ("marketing, business, or related area", 4, 6, 1), None),
            ("12200", "Full time", 118000, 225000, "Regular/Permanent",
             ("electrical engineering, product design, or related area", 5, 8, 3), None),
        ],
    },
    {
        "title": "Director, Product Management",
        "area": "technology",
        "category": "Product Management",
        "shifts": "WD,SD",
        "summary": "Lead a portfolio of product areas and the managers who run them.",
        "do": [
            "Directors of Product Management at {location_name} in {city}, {state} set direction for a "
            "portfolio, hire and develop product managers, and represent the portfolio in company-level "
            "planning.",
            "You will spend your time on strategy, talent and unblocking - not on writing every "
            "requirement yourself.",
        ],
        "about_team": "This portfolio spans several teams working on connected customer experiences.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "product management or related area, including {yp} years of people leadership.",
        "min_qual_option2": "Option 2: {y2} years' experience in product management or related area, "
                            "including {yp} years of people leadership.",
        "preferred": "Master's degree in business administration and experience owning a profit and loss "
                     "statement for {yp} years or more.",
        "placements": [
            ("10101", "Full time", 130000, 260000, "Regular/Permanent",
             ("business, engineering, or related area", 8, 11, 4), None),
            ("12200", "Full time", 125000, 245000, "Regular/Permanent",
             ("electrical engineering, business, or related area", 7, 10, 4), None),
        ],
    },
    {
        "title": "Senior Data Scientist",
        "area": "technology",
        "category": "Data Science and Analytics",
        "shifts": "WD",
        "summary": "Build models that change what customers see and what the business decides.",
        "do": [
            "Senior Data Scientists at {location_name} in {city}, {state} frame the problem, build the "
            "model, ship it behind an experiment, and tell the story of what it did.",
            "You will work in Python and SQL against very large datasets, and you will be expected to "
            "defend your methodology to people who will use the results.",
        ],
        "about_team": "Data science sits inside the product teams here, not in a separate lab.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "an analytics or data science role.",
        "min_qual_option2": "Option 2: {y2} years' experience in an analytics or data science role.",
        "preferred": "Master's or PhD in {degree_field} and {yp} years' experience deploying models to "
                     "production.",
        "placements": [
            ("10101", "Full time", 108000, 216000, "Regular/Permanent",
             ("statistics, economics, computer science, or related area", 4, 6, 2), None),
            ("11807", "Full time", 130000, 260000, "Regular/Permanent",
             ("machine learning, statistics, or related area", 5, 8, 3), None),
            ("11003", "Full time", 110000, 190000, "Regular/Permanent",
             ("applied mathematics, statistics, or related area", 3, 5, 1), None),
            ("11500", "Full time", 100000, 175000, "Regular/Permanent",
             ("operations research, statistics, or related area", 3, 6, 2), None),
            ("12200", "Full time", 112000, 205000, "Regular/Permanent",
             ("data science, statistics, or related area", 4, 7, 2), None),
        ],
    },
    {
        "title": "Senior Manager, Information Security",
        "area": "technology",
        "category": "Information Security",
        "shifts": "WD,SD",
        "summary": "Lead a security function protecting customer and associate data at scale.",
        "do": [
            "Senior Managers of Information Security at {location_name} in {city}, {state} lead a security "
            "team, set the control standard for their domain, and partner with engineering on how those "
            "controls actually get implemented.",
            "You will own incident response readiness for your area and report risk posture to leadership "
            "on a regular cadence.",
        ],
        "about_team": "Information security here is embedded with the teams it protects.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "information security or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in information security or related area.",
        "preferred": "CISSP or equivalent certification and {yp} years' experience leading security teams.",
        "placements": [
            ("10101", "Full time", 115000, 230000, "Regular/Permanent",
             ("information technology, cybersecurity, or related area", 5, 8, 3), None),
            ("11807", "Full time", 140000, 280000, "Regular/Permanent",
             ("computer science, cybersecurity, or related area", 6, 9, 4), None),
            ("12200", "Full time", 122000, 235000, "Regular/Permanent",
             ("information assurance, computer science, or related area", 4, 7, 3), None),
        ],
    },
    {
        "title": "Information Security Engineer III",
        "area": "technology",
        "category": "Information Security",
        "shifts": "WD",
        "summary": "Engineer and operate the detection and prevention controls that protect the platform.",
        "do": [
            "Security Engineers at {location_name} in {city}, {state} build detections, tune controls, and "
            "work incidents alongside the response team.",
            "You will write code, not just configure tools, and you will be on a rotation.",
        ],
        "about_team": "This team keeps the platform defensible as it changes weekly.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "information security or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in information security or related area.",
        "preferred": "Experience with cloud security tooling and {yp} years' experience in detection "
                     "engineering.",
        "placements": [
            ("11003", "Full time", 80000, 160000, "Regular/Permanent",
             ("cybersecurity, information systems, or related area", 2, 4, 1), None),
            ("12200", "Full time", 95000, 170000, "Regular/Permanent",
             ("computer engineering, cybersecurity, or related area", 3, 5, 2), None),
        ],
    },
    {
        "title": "Senior UX Designer",
        "area": "technology",
        "category": "Creative Design and UX",
        "shifts": "WD",
        "summary": "Design flows that millions of people use without thinking about them.",
        "do": [
            "Senior UX Designers at {location_name} in {city}, {state} own the experience for a product "
            "area: research synthesis, flows, prototypes and the detailed specs engineering builds from.",
            "You will test your work with real customers and change it when the test says so.",
        ],
        "about_team": "Design partners directly with product and engineering from the first week of a "
                      "project.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "user experience design or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in user experience design or related area.",
        "preferred": "A portfolio showing shipped consumer work and {yp} years' experience with design "
                     "systems.",
        "placements": [
            ("11807", "Full time", 120000, 240000, "Regular/Permanent",
             ("design, human-computer interaction, or related area", 5, 7, 3), None),
            ("11003", "Full time", 96000, 186000, "Regular/Permanent",
             ("interaction design, visual design, or related area", 3, 6, 2), None),
            ("12200", "Full time", 88000, 165000, "Regular/Permanent",
             ("industrial design, human factors, or related area", 3, 5, 2), None),
        ],
    },
    {
        "title": "Principal UX Researcher",
        "area": "technology",
        "category": "Creative Design and UX",
        "shifts": "WD",
        "summary": "Set the research agenda for a large product organization.",
        "do": [
            "Principal UX Researchers at {location_name} in {city}, {state} decide what the organization "
            "needs to learn next, design the studies that answer it, and make sure the answer changes "
            "what gets built.",
            "You will mentor researchers across teams and raise the methodological bar for everyone.",
        ],
        "about_team": "Research here reports into design and works across several product areas at once.",
        "min_qual_option1": "Option 1: Master's degree in {degree_field} and {y1} years' experience in "
                            "user research or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in user research or related area.",
        "preferred": "PhD in {degree_field} and {yp} years' experience leading mixed-methods research "
                     "programs.",
        "placements": [
            ("11807", "Full time", 150000, 275000, "Regular/Permanent",
             ("psychology, human-computer interaction, or related area", 7, 10, 4), None),
            ("12200", "Full time", 138000, 255000, "Regular/Permanent",
             ("cognitive science, design research, or related area", 6, 9, 3), None),
        ],
    },
    {
        "title": "Senior Technical Program Manager",
        "area": "technology",
        "category": "Technical Program Management",
        "shifts": "WD",
        "summary": "Drive cross-team technical programs from commitment to launch.",
        "do": [
            "Senior Technical Program Managers at {location_name} in {city}, {state} own the plan, the "
            "risks and the communication for programs that span several engineering teams.",
            "You will be technical enough to challenge an estimate and organized enough that nobody has "
            "to ask you for a status.",
        ],
        "about_team": "Technical program management sits with engineering leadership here.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "technical program management or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in technical program management or related "
                            "area.",
        "preferred": "Experience running programs across distributed teams for {yp} years or more.",
        "placements": [
            ("11807", "Full time", 125000, 250000, "Regular/Permanent",
             ("engineering, computer science, or related area", 5, 8, 3), None),
            ("10101", "Full time", 105000, 210000, "Regular/Permanent",
             ("information systems, engineering, or related area", 4, 7, 2), None),
            ("12200", "Full time", 92000, 175000, "Regular/Permanent",
             ("electrical engineering, computer science, or related area", 3, 6, 2), None),
            ("11003", "Full time", 99000, 195000, "Regular/Permanent",
             ("industrial engineering, business, or related area", 4, 6, 2), None),
        ],
    },
    {
        "title": "IT Support Engineer",
        "area": "technology",
        "category": "Information Technology",
        "shifts": "WD,SD",
        "summary": "Keep the people who work here productive, from laptops to conference rooms.",
        "do": [
            "IT Support Engineers at {location_name} in {city}, {state} handle escalated endpoint, "
            "identity and collaboration issues for the associates on site.",
            "You will automate the repeat offenders instead of fixing them one ticket at a time.",
        ],
        "about_team": "Workplace technology supports every associate in the building.",
        "min_qual_option1": "Option 1: Associate's degree in {degree_field} and {y1} years' experience in "
                            "information technology support or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in information technology support or "
                            "related area.",
        "preferred": "Scripting experience and {yp} years' experience with endpoint management tooling.",
        "placements": [
            ("10101", "Full time", 70000, 140000, "Regular/Permanent",
             ("information technology or related area", 2, 4, 2), None),
            ("11500", "Full time", 68000, 136000, "Regular/Permanent",
             ("computer information systems or related area", 2, 5, 1), None),
            ("12200", "Full time", 72000, 144000, "Regular/Permanent",
             ("network administration or related area", 3, 5, 2), None),
            ("11109", "Full time", 66000, 132000, "Regular/Permanent",
             ("information systems or related area", 1, 3, 1), None),
        ],
    },
    {
        "title": "Senior Manager, Finance",
        "area": "corporate",
        "category": "Accounting and Finance",
        "shifts": "WD",
        "summary": "Lead financial planning and analysis for a business unit.",
        "do": [
            "Senior Managers of Finance at {location_name} in {city}, {state} run the planning cycle for "
            "their business unit, build the models leadership decides from, and lead a small team of "
            "analysts.",
            "You will be in the room when the trade-offs are made, and you will be expected to have a "
            "point of view.",
        ],
        "about_team": "Finance partners are embedded with the businesses they support.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "accounting, finance or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in accounting, finance or related area.",
        "preferred": "CPA or MBA and {yp} years' experience leading finance teams.",
        "placements": [
            ("10101", "Full time", 100000, 200000, "Regular/Permanent",
             ("accounting, finance, or related area", 5, 7, 3), None),
            ("11500", "Full time", 90000, 180000, "Regular/Permanent",
             ("finance, economics, or related area", 4, 6, 2), None),
            ("12200", "Full time", 98000, 190000, "Regular/Permanent",
             ("corporate finance, accounting, or related area", 3, 5, 2), None),
        ],
    },
    {
        "title": "Financial Analyst III",
        "area": "corporate",
        "category": "Accounting and Finance",
        "shifts": "WD",
        "summary": "Build the forecasts, variance analysis and business cases the team runs on.",
        "do": [
            "Financial Analysts at {location_name} in {city}, {state} own a piece of the forecast, explain "
            "variances to plan, and build the business cases that support investment decisions.",
            "You will live in spreadsheets and the planning system, and you will present your work "
            "directly to business leaders.",
        ],
        "about_team": "This team supports one of the largest cost centers in the company.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "financial analysis or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in financial analysis or related area.",
        "preferred": "Advanced modelling skills and {yp} years' experience in a retail or supply chain "
                     "finance team.",
        "placements": [
            ("10101", "Full time", 70000, 130000, "Regular/Permanent",
             ("finance, accounting, or related area", 2, 4, 2), None),
            ("11109", "Full time", 68000, 126000, "Regular/Permanent",
             ("accounting, business, or related area", 2, 5, 1), None),
            ("11500", "Full time", 72000, 134000, "Regular/Permanent",
             ("economics, finance, or related area", 3, 5, 2), None),
            ("12200", "Full time", 71000, 132000, "Regular/Permanent",
             ("finance, business analytics, or related area", 1, 3, 1), None),
        ],
    },
    {
        "title": "Senior Manager, People Partner",
        "area": "corporate",
        "category": "Human Resources",
        "shifts": "WD",
        "summary": "Partner with business leaders on talent, org design and associate experience.",
        "do": [
            "Senior Managers, People Partner at {location_name} in {city}, {state} advise leaders on "
            "organisation design, talent planning and the hard conversations, and own the people plan for "
            "their client group.",
            "You will use data as well as judgement, and you will be the person associates trust to be "
            "straight with them.",
        ],
        "about_team": "People partners support the business teams in the building directly.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "human resources or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in human resources or related area.",
        "preferred": "SHRM-SCP certification and {yp} years' experience supporting technology "
                     "organisations.",
        "placements": [
            ("10101", "Full time", 96000, 186000, "Regular/Permanent",
             ("human resources, business, or related area", 5, 7, 3), None),
            ("11003", "Full time", 100000, 195000, "Regular/Permanent",
             ("industrial relations, psychology, or related area", 4, 6, 2), None),
        ],
    },
    {
        "title": "HR Business Partner",
        "area": "corporate",
        "category": "Human Resources",
        "shifts": "WD",
        "summary": "Support a client group across hiring, performance and associate relations.",
        "do": [
            "HR Business Partners at {location_name} in {city}, {state} run the people cycle for their "
            "client group: hiring plans, performance calibration, development and associate relations "
            "cases.",
            "You will coach managers who are new to leading people and hold the line on policy when it "
            "matters.",
        ],
        "about_team": "This team supports several hundred associates across the site.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "human resources or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in human resources or related area.",
        "preferred": "Experience with associate relations investigations for {yp} years or more.",
        "placements": [
            ("11500", "Full time", 80000, 150000, "Regular/Permanent",
             ("human resources or related area", 3, 5, 2), None),
            ("11109", "Full time", 78000, 146000, "Regular/Permanent",
             ("business administration or related area", 2, 4, 1), None),
            ("12200", "Full time", 82000, 152000, "Regular/Permanent",
             ("organizational psychology, human resources, or related area", 4, 6, 2), None),
        ],
    },
    {
        "title": "Manager, Marketing",
        "area": "corporate",
        "category": "Marketing and Advertising",
        "shifts": "WD",
        "summary": "Own campaign strategy and execution for a product line.",
        "do": [
            "Marketing Managers at {location_name} in {city}, {state} own the plan for a product line: "
            "positioning, campaign calendar, agency briefs and the results readout.",
            "You will work with creative, media and analytics, and you will be accountable for what the "
            "spend returned.",
        ],
        "about_team": "Marketing here works close to the product teams and the sales calendar.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "marketing or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in marketing or related area.",
        "preferred": "Experience running integrated consumer campaigns for {yp} years or more.",
        "placements": [
            ("12200", "Full time", 85000, 160000, "Regular/Permanent",
             ("marketing, communications, or related area", 3, 5, 2), None),
            ("10101", "Full time", 90000, 170000, "Regular/Permanent",
             ("marketing, business, or related area", 4, 6, 3), None),
        ],
    },
    {
        "title": "Senior Manager, Brand Marketing",
        "area": "corporate",
        "category": "Marketing and Advertising",
        "shifts": "WD",
        "summary": "Lead brand strategy and the campaigns that carry it.",
        "do": [
            "Senior Managers of Brand Marketing at {location_name} in {city}, {state} own how the brand "
            "shows up: the platform, the creative standard and the campaigns that put it in front of "
            "customers.",
            "You will lead a small team and manage agency partners against a real budget.",
        ],
        "about_team": "Brand marketing sets the standard the rest of marketing works to.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "brand or consumer marketing.",
        "min_qual_option2": "Option 2: {y2} years' experience in brand or consumer marketing.",
        "preferred": "Master's degree in business administration and {yp} years' experience managing "
                     "agency relationships.",
        "placements": [
            ("10101", "Full time", 110000, 210000, "Regular/Permanent",
             ("marketing, advertising, or related area", 6, 8, 3), None),
            ("11500", "Full time", 105000, 200000, "Regular/Permanent",
             ("communications, marketing, or related area", 5, 7, 2), None),
            ("12200", "Full time", 102000, 196000, "Regular/Permanent",
             ("brand management, marketing, or related area", 4, 6, 2), None),
        ],
    },
    {
        "title": "Marketing Specialist III",
        "area": "corporate",
        "category": "Marketing and Advertising",
        "shifts": "WD",
        "summary": "Execute member marketing programs and report on what they returned.",
        "do": [
            "Marketing Specialists at {location_name} in {city}, {state} execute the member marketing "
            "calendar: briefs, asset trafficking, channel setup and post-campaign reporting.",
            "You will keep several campaigns moving at once and be the person who notices the detail "
            "everyone else missed.",
        ],
        "about_team": "Member marketing owns how the club talks to its members between visits.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "marketing or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in marketing or related area.",
        "preferred": "Experience with customer relationship management platforms for {yp} years or more.",
        "placements": [
            ("11109", "Full time", 65000, 120000, "Regular/Permanent",
             ("marketing or related area", 2, 4, 1), None),
            ("12200", "Full time", 68000, 126000, "Regular/Permanent",
             ("marketing, media studies, or related area", 3, 5, 2), None),
        ],
    },
    {
        "title": "Senior Buyer",
        "area": "corporate",
        "category": "Merchandising",
        "shifts": "WD",
        "summary": "Own assortment, cost and supplier relationships for a category.",
        "do": [
            "Senior Buyers at {location_name} in {city}, {state} own a category: what we carry, what we "
            "pay for it, and how it performs on the floor.",
            "You will negotiate with suppliers, build the assortment plan by season, and answer for the "
            "category's sales and margin every month.",
        ],
        "about_team": "Merchandising decides what ends up on the shelf and at what price.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "merchandising, buying or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in merchandising, buying or related area.",
        "preferred": "Experience negotiating national supplier agreements for {yp} years or more.",
        "placements": [
            ("10101", "Full time", 95000, 185000, "Regular/Permanent",
             ("business, merchandising, or related area", 5, 7, 3), None),
            ("11109", "Full time", 92000, 178000, "Regular/Permanent",
             ("supply chain, business, or related area", 4, 6, 2), None),
        ],
    },
    {
        "title": "Merchandising Manager",
        "area": "corporate",
        "category": "Merchandising",
        "shifts": "WD",
        "summary": "Turn category strategy into the plan the stores and clubs actually execute.",
        "do": [
            "Merchandising Managers at {location_name} in {city}, {state} translate category strategy into "
            "modulars, promotions and in-club execution plans.",
            "You will work with buyers, replenishment and field leadership to make sure the plan survives "
            "contact with the sales floor.",
        ],
        "about_team": "This team bridges the buying office and the buildings.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "merchandising or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in merchandising or related area.",
        "preferred": "Field retail experience and {yp} years' experience with space planning tools.",
        "placements": [
            ("10101", "Full time", 88000, 170000, "Regular/Permanent",
             ("merchandising, business, or related area", 4, 6, 2), None),
            ("11109", "Full time", 85000, 165000, "Regular/Permanent",
             ("retail management, business, or related area", 3, 5, 2), None),
        ],
    },
    {
        "title": "Replenishment Manager",
        "area": "corporate",
        "category": "Merchandising",
        "shifts": "WD",
        "summary": "Own in-stock and inventory turns for a category across the network.",
        "do": [
            "Replenishment Managers at {location_name} in {city}, {state} own in-stock, forecast accuracy "
            "and inventory turns for their categories across the whole network.",
            "You will tune forecasting parameters, work supplier lead times, and be the first call when a "
            "category goes out of stock in a region.",
        ],
        "about_team": "Replenishment keeps thousands of buildings full without drowning them in "
                      "inventory.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "replenishment, supply chain or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in replenishment, supply chain or related "
                            "area.",
        "preferred": "Experience with demand forecasting systems for {yp} years or more.",
        "placements": [
            ("10101", "Full time", 84000, 162000, "Regular/Permanent",
             ("supply chain, industrial engineering, or related area", 4, 6, 2), None),
        ],
    },
    {
        "title": "Senior Manager, Delivery Search, Arrival & Matching (Last Mile Delivery)",
        "area": "corporate",
        "category": "Business Operations",
        "shifts": "WD,SD",
        "summary": "Own the operations behind driver matching and arrival accuracy for last mile delivery.",
        "do": [
            "Senior Managers on Last Mile Delivery at {location_name} in {city}, {state} own the "
            "operational levers behind delivery search, driver arrival and order matching: the policies, "
            "the thresholds and the escalation paths that keep deliveries on time.",
            "You will work with product and data science on where the model ends and operations begins, "
            "and you will own the metric either way.",
        ],
        "about_team": "Last Mile Delivery moves millions of orders from the building to the doorstep.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "operations management or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in operations management or related area.",
        "preferred": "Master's degree in {degree_field} and {yp} years' experience in last mile or "
                     "transportation operations.",
        "placements": [
            ("10101", "Full time", 110000, 220000, "Regular/Permanent",
             ("supply chain management, operations, or related area", 6, 9, 3),
             {"job_id": "R-2456729",
              "qual_clause": "including experience running a last mile delivery or courier network"}),
            ("11003", "Full time", 117000, 234000, "Regular/Permanent",
             ("industrial engineering, logistics, or related area", 4, 6, 2),
             {"qual_clause": "including experience with driver dispatch or arrival-time modeling"}),
        ],
    },
    {
        "title": "Manager, Supply Chain Operations",
        "area": "corporate",
        "category": "Business Operations",
        "shifts": "WD",
        "summary": "Run network planning and continuous improvement for a supply chain region.",
        "do": [
            "Managers of Supply Chain Operations at {location_name} in {city}, {state} own network "
            "planning, cost-to-serve analysis and continuous improvement projects for their region.",
            "You will spend time in the buildings, not only in the model, and you will bring changes back "
            "that the operators can actually run.",
        ],
        "about_team": "Supply chain operations connects the network plan to what happens on the dock.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "supply chain or operations.",
        "min_qual_option2": "Option 2: {y2} years' experience in supply chain or operations.",
        "preferred": "Lean or Six Sigma certification and {yp} years' experience leading improvement "
                     "projects.",
        "placements": [
            ("11500", "Full time", 82000, 158000, "Regular/Permanent",
             ("supply chain management or related area", 3, 5, 2), None),
            ("10101", "Full time", 86000, 166000, "Regular/Permanent",
             ("industrial engineering, logistics, or related area", 4, 6, 2), None),
            ("12200", "Full time", 88000, 168000, "Regular/Permanent",
             ("operations management, logistics, or related area", 2, 4, 1), None),
        ],
    },
    {
        "title": "Business Operations Analyst III",
        "area": "corporate",
        "category": "Business Operations",
        "shifts": "WD",
        "summary": "Turn operational data into the decisions the business runs on.",
        "do": [
            "Business Operations Analysts at {location_name} in {city}, {state} build the reporting, run "
            "the analysis and write the recommendation that leadership acts on.",
            "You will be trusted with the numbers, which means you will be the one who has to catch the "
            "mistake in them.",
        ],
        "about_team": "Business operations supports planning and performance management across the site.",
        "min_qual_option1": "Option 1: Bachelor's degree in {degree_field} and {y1} years' experience in "
                            "business analysis or related area.",
        "min_qual_option2": "Option 2: {y2} years' experience in business analysis or related area.",
        "preferred": "Advanced SQL and visualization experience for {yp} years or more.",
        "placements": [
            ("11500", "Full time", 66000, 122000, "Regular/Permanent",
             ("business analytics, economics, or related area", 2, 4, 1), None),
            ("12200", "Full time", 70000, 128000, "Regular/Permanent",
             ("operations analytics, business, or related area", 3, 5, 2), None),
        ],
    },
    {
        "title": "Merchandising Intern",
        "area": "students",
        "category": "Internship",
        "shifts": "WD",
        "summary": "A paid summer internship inside a buying office, owning a real category project.",
        "do": [
            "Merchandising Interns at {location_name} in {city}, {state} join a buying team for the summer "
            "and own one category project end to end, from the data pull to the recommendation.",
            "You will sit in supplier meetings, walk buildings with the field team, and present your "
            "recommendation to merchandising leadership at the end of the program.",
        ],
        "about_team": "The internship program places students directly on the teams that make the "
                      "decisions.",
        "min_qual_option1": "Option 1: Currently enrolled in a bachelor's degree program in {degree_field} "
                            "with an expected graduation date within {y1} years.",
        "min_qual_option2": "Option 2: Currently enrolled in a master's degree program in {degree_field} "
                            "with an expected graduation date within {y2} years.",
        "preferred": "Coursework or prior internship experience in retail merchandising within the last "
                     "{yp} years.",
        "placements": [
            ("11109", "Intern", 64000, 90000, "Intern (Fixed Term)",
             ("business, marketing, or supply chain", 2, 1, 2), None),
            ("10101", "Intern", 66000, 92000, "Intern (Fixed Term)",
             ("business administration or merchandising", 2, 1, 1), None),
            ("11500", "Intern", 62000, 88000, "Intern (Fixed Term)",
             ("business, merchandising, or analytics", 1, 2, 1), None),
        ],
    },
    {
        "title": "Software Engineering Intern",
        "area": "students",
        "category": "Internship",
        "shifts": "WD",
        "summary": "A paid summer internship writing production code on a platform team.",
        "do": [
            "Software Engineering Interns at {location_name} in {city}, {state} join a platform team, take "
            "a real ticket in week one, and ship code to production before the summer is over.",
            "You will have an engineering mentor, take part in code review, and present your project at "
            "the end of the program.",
        ],
        "about_team": "Interns join the same teams and the same rituals as full-time engineers.",
        "min_qual_option1": "Option 1: Currently enrolled in a bachelor's degree program in {degree_field} "
                            "with an expected graduation date within {y1} years.",
        "min_qual_option2": "Option 2: Currently enrolled in a master's degree program in {degree_field} "
                            "with an expected graduation date within {y2} years.",
        "preferred": "Coursework in data structures and algorithms and {yp} prior software internship.",
        "placements": [
            ("11807", "Intern", 78000, 104000, "Intern (Fixed Term)",
             ("computer science or computer engineering", 2, 1, 1), None),
            ("10101", "Intern", 72000, 98000, "Intern (Fixed Term)",
             ("computer science or information systems", 1, 2, 1), None),
            ("11003", "Intern", 76000, 102000, "Intern (Fixed Term)",
             ("software engineering or computer engineering", 3, 2, 1), None),
        ],
    },
    {
        "title": "Finance Intern",
        "area": "students",
        "category": "Internship",
        "shifts": "WD",
        "summary": "A paid summer internship on a finance planning team.",
        "do": [
            "Finance Interns at {location_name} in {city}, {state} support a planning team through a full "
            "forecast cycle and own one analysis that goes in front of a business leader.",
            "You will learn the planning system, the reporting stack and how the company actually decides "
            "where money goes.",
        ],
        "about_team": "Finance interns sit with the teams they support, not in a separate cohort room.",
        "min_qual_option1": "Option 1: Currently enrolled in a bachelor's degree program in {degree_field} "
                            "with an expected graduation date within {y1} years.",
        "min_qual_option2": "Option 2: Currently enrolled in a master's degree program in {degree_field} "
                            "with an expected graduation date within {y2} years.",
        "preferred": "Coursework in financial modelling and {yp} prior finance internship.",
        "placements": [
            ("10101", "Intern", 60000, 84000, "Intern (Fixed Term)",
             ("finance, accounting, or economics", 2, 1, 1), None),
            ("11500", "Intern", 58000, 82000, "Intern (Fixed Term)",
             ("accounting or business administration", 1, 2, 1), None),
        ],
    },
    {
        "title": "Data Analytics Intern",
        "area": "students",
        "category": "Internship",
        "shifts": "WD",
        "summary": "A paid summer internship on an analytics team supporting eCommerce.",
        "do": [
            "Data Analytics Interns at {location_name} in {city}, {state} join an analytics team, build a "
            "dashboard or model that a business owner asked for, and hand it over working.",
            "You will use SQL and Python daily and present your findings at the end of the program.",
        ],
        "about_team": "Analytics here reports into the product organisation it supports.",
        "min_qual_option1": "Option 1: Currently enrolled in a bachelor's degree program in {degree_field} "
                            "with an expected graduation date within {y1} years.",
        "min_qual_option2": "Option 2: Currently enrolled in a master's degree program in {degree_field} "
                            "with an expected graduation date within {y2} years.",
        "preferred": "Coursework in statistics or machine learning and {yp} prior analytics internship.",
        "placements": [
            ("11003", "Intern", 70000, 96000, "Intern (Fixed Term)",
             ("statistics, data science, or economics", 2, 1, 1), None),
            ("11807", "Intern", 74000, 100000, "Intern (Fixed Term)",
             ("computer science, statistics, or mathematics", 1, 3, 1), None),
        ],
    },
]


# --------------------------------------------------------------------------- #
# Hub copy for the four is_hub offices, keyed by store number:
# (display name, blurb, image file). Seeded onto Store.hub_name / hub_blurb /
# hub_image so the locations and career-area templates read it from the DB.
# --------------------------------------------------------------------------- #
HUB_COPY = {
    "10101": (
        "Northwest Arkansas",
        "Northwest Arkansas offers trails, local eats, and the Crystal Bridges Museum - while our "
        "12 new Home Office buildings reflect the company's story through thoughtful design.",
        "loc-nwa.jpg",
    ),
    "11807": (
        "Sunnyvale",
        "A weekend hike through the mountains. An evening walk next to the ocean. A quick visit to a "
        "museum. The best of both worlds - work and leisure - are waiting for you right here.",
        "loc-sunnyvale.jpg",
    ),
    "11003": (
        "Hoboken",
        "Just across from Lower Manhattan, Hoboken is a walkable, character-filled town on the Hudson "
        "with a truly unique charm.",
        "loc-hoboken.jpg",
    ),
    "11500": (
        "Dallas",
        "Our Dallas office anchors merchandising, finance and supply chain teams in the middle of one "
        "of the fastest-growing metros in the country.",
        "loc-dallas.jpg",
    ),
}


# --------------------------------------------------------------------------- #
# Job ids surfaced as "Trending roles" on the home page, the hiring page and the
# logged-out saved-roles page. Seeded onto Job.is_trending, which is what the
# handlers query. These three placements pin their job_id in `extras` so a
# catalog edit cannot silently point this list at a different posting.
# --------------------------------------------------------------------------- #
TRENDING_JOB_IDS = [
    "R-2418512",
    "R-2417063",
    "CP-1236-10741",
]


# --------------------------------------------------------------------------- #
# "What you'll bring" bullets for salaried postings, one template list per
# category. Slot fills are location only ({city}, {state}, {location_name}); the
# bullets deliberately never mention a degree or a number of years, which live
# solely in the Minimum Qualifications block.
# --------------------------------------------------------------------------- #
SALARIED_BRING = {
    "Software Engineering and Architecture": [
        "A track record of designing, building and operating production services that hold up at retail traffic.",
        "Fluency in at least one modern backend language and its ecosystem, plus comfort reading code in others.",
        "Hands-on experience with distributed data stores, message queues and cloud infrastructure.",
        "A test-driven approach to development and a strong commitment to code quality and documentation.",
        "Clear written and spoken communication with engineers, product managers and partners across {city}.",
    ],
    "Product Management": [
        "Experience owning a product area end to end, from discovery through launch and iteration.",
        "The ability to turn ambiguous customer problems into a crisp roadmap and measurable outcomes.",
        "Comfort working daily with engineering, design and data science partners in {city}.",
        "Strong written communication, including product specs and executive updates.",
    ],
    "Data Science and Analytics": [
        "Hands-on experience building and shipping statistical or machine learning models in production.",
        "Fluency in Python or R and SQL, and comfort working with very large datasets.",
        "The judgment to know when a simple model beats a complex one.",
        "Experience explaining findings to non-technical partners across the {city} office.",
    ],
    "Information Security": [
        "Deep familiarity with threat modeling, secure design review and incident response.",
        "Experience with identity, access management and cloud security controls at scale.",
        "The ability to translate risk into priorities that engineering teams can act on.",
        "Calm, clear communication during live incidents.",
    ],
    "Creative Design and UX": [
        "A portfolio that shows end-to-end design work, from research through shipped experience.",
        "Fluency in modern design and prototyping tools and a working knowledge of front-end constraints.",
        "Experience planning and running user research and turning it into design decisions.",
        "The ability to present and defend design decisions to partners in {city}.",
    ],
    "Technical Program Management": [
        "Experience running large cross-functional programs with many engineering teams.",
        "Enough technical depth to challenge estimates and spot dependencies early.",
        "A bias for clear plans, visible risks and honest status.",
        "Strong facilitation skills across the {city} office and remote partners.",
    ],
    "Information Technology": [
        "Experience supporting enterprise endpoints, identity systems and collaboration tools.",
        "Scripting skills for automating repetitive support and provisioning tasks.",
        "A customer-first approach to troubleshooting and a habit of documenting fixes.",
        "Comfort supporting associates on site in {city} and remotely.",
    ],
    "Accounting and Finance": [
        "Experience owning forecasts, budgets or close processes for a large business unit.",
        "Advanced spreadsheet and financial modeling skills, plus comfort with planning systems.",
        "The ability to explain variances to operators and executives in plain language.",
        "Attention to detail and a strong sense of ownership over the numbers.",
    ],
    "Human Resources": [
        "Experience partnering with leaders on talent, organization design and associate relations.",
        "Working knowledge of employment practices and the judgment to apply them fairly.",
        "Strong coaching and facilitation skills.",
        "Comfort supporting teams across the {city} office and the field.",
    ],
    "Marketing and Advertising": [
        "Experience planning and running integrated campaigns across digital and in-store channels.",
        "Fluency in campaign measurement and the ability to act on what the data says.",
        "Strong creative judgment and clear briefing skills for agency and in-house partners.",
        "Comfort presenting plans and results to senior leaders in {city}.",
    ],
    "Merchandising": [
        "Experience owning assortment, pricing or replenishment decisions for a category.",
        "Strong analytical skills and comfort working in large planning and forecasting systems.",
        "The ability to negotiate with suppliers and build long-term partnerships.",
        "A customer-first mindset and a habit of walking the stores.",
    ],
    "Business Operations": [
        "Experience owning operational metrics and the processes behind them.",
        "Strong analytical skills, including the ability to build and interpret operational dashboards.",
        "Comfort working across product, data science and field operations partners.",
        "A habit of spending time where the work happens, not only in the model.",
    ],
    "Internship": [
        "Current enrollment in a degree program with an expected graduation date after the internship term.",
        "Curiosity about how a large retailer runs and a willingness to ask questions.",
        "Comfort working in a team and presenting your project to leaders in {city}.",
        "Availability for the full internship term.",
    ],
}
