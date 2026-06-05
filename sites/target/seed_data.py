"""Deterministic seed data for the Target WebHarbor mirror."""

from __future__ import annotations

import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from app import (
    BENCHMARK_PASSWORD,
    Brand,
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
    RewardAccount,
    RewardActivity,
    SearchLog,
    Store,
    StoreInventory,
    SupportArticle,
    SupportTicket,
    User,
    WishlistItem,
    db,
    dump_json,
    slugify,
)


SEED_TIMESTAMP = datetime(2026, 3, 18, 10, 0, 0)
RNG = random.Random(20260604)
EXPECTED_COUNTS = {
    "users": 4,
    "categories": 12,
    "brands": 25,
    "products": 150,
    "stores": 15,
    "inventory": 500,
    "reviews": 250,
    "orders": 60,
}

CATEGORY_COLORS = {
    "laptops": ("#0b2242", "#2878ff", "#fff200"),
    "tvs-home-theater": ("#10141d", "#006ce0", "#ffdc47"),
    "tablets": ("#08264d", "#0d86ff", "#ffe563"),
    "cameras": ("#151a21", "#2a65f7", "#f8cd32"),
    "headphones": ("#091828", "#0b74ff", "#f6d74a"),
    "gaming": ("#13181f", "#3a6cff", "#ffe44f"),
    "smart-home": ("#0f2238", "#1d8cff", "#f3e051"),
    "monitors": ("#111825", "#2f6ef8", "#ffe152"),
    "storage-networking": ("#10233b", "#2276ff", "#ffe863"),
    "appliances": ("#13233a", "#246fff", "#ffdb56"),
    "phones-wearables": ("#0a223e", "#146eff", "#ffe35a"),
    "printers-office": ("#15202d", "#2f79ff", "#ffe76c"),
}


BRANDS = [
    ("Apple", "#888f9c"),
    ("Samsung", "#0b6dff"),
    ("LG", "#b10659"),
    ("Sony", "#1b1b1b"),
    ("Dell", "#1273ea"),
    ("HP", "#0096d6"),
    ("Lenovo", "#e2231a"),
    ("Asus", "#0050c8"),
    ("Acer", "#6abf4b"),
    ("Bose", "#4c5968"),
    ("Canon", "#c51f1a"),
    ("Nikon", "#d3a400"),
    ("Nintendo", "#e60012"),
    ("Microsoft", "#737373"),
    ("JBL", "#ff6600"),
    ("Dyson", "#8c3997"),
    ("Belkin", "#3e7dd1"),
    ("WD", "#1864ff"),
    ("TCL", "#ff4d2d"),
    ("Insignia", "#0046be"),
    ("GoPro", "#0d6efd"),
    ("Garmin", "#007cc3"),
    ("Epson", "#1f4aa8"),
    ("Brother", "#15284b"),
    ("Logitech", "#00b8fc"),
]


CATEGORIES = [
    {
        "slug": "laptops",
        "name": "Tech & Office Laptops",
        "section": "Electronics & Office",
        "description": "Work-from-home laptops, student notebooks, and creator-ready computers with local demo specs.",
        "hero_title": "Upgrade your desk with demo laptops, study essentials, and pickup-friendly tech.",
    },
    {
        "slug": "tvs-home-theater",
        "name": "TVs & Entertainment",
        "section": "Electronics",
        "description": "4K TVs, streaming-ready displays, and living-room gear with pickup and delivery options.",
        "hero_title": "Big screens, bold deal badges, and synthetic store stock that resets instantly.",
    },
    {
        "slug": "tablets",
        "name": "Tablets & Reading",
        "section": "Electronics",
        "description": "Portable screens for note-taking, streaming, family travel, and reading.",
        "hero_title": "Find the right size, storage tier, and family-friendly accessories in one local catalog.",
    },
    {
        "slug": "cameras",
        "name": "Cameras & Content Creation",
        "section": "Electronics",
        "description": "Mirrorless cameras, action cams, and creator bundles with deep specs.",
        "hero_title": "Local demo cameras with pickup-ready bundles and compare-friendly specs.",
    },
    {
        "slug": "headphones",
        "name": "Audio & Headphones",
        "section": "Tech",
        "description": "Headphones, earbuds, and speakers with review-rich pages and pickup eligibility.",
        "hero_title": "Tune into rich product details, reviews, and warranty choices.",
    },
    {
        "slug": "gaming",
        "name": "Video Games & Gear",
        "section": "Toys & Entertainment",
        "description": "Consoles, controllers, displays, and accessories with pickup eligibility filters.",
        "hero_title": "Search for consoles, compare gear, and check store pickup without real inventory.",
    },
    {
        "slug": "smart-home",
        "name": "Smart Home",
        "section": "Home",
        "description": "Cameras, thermostats, hubs, and connected lighting for support-heavy tasks.",
        "hero_title": "Find setup help, curbside pickup advice, and smart-home essentials in one place.",
    },
    {
        "slug": "monitors",
        "name": "Monitors & Desk Setup",
        "section": "Electronics & Office",
        "description": "Gaming, office, and creator monitors with size, refresh rate, and panel filters.",
        "hero_title": "Compare refresh rates, panel types, and store pickup at a glance.",
    },
    {
        "slug": "storage-networking",
        "name": "Storage & Accessories",
        "section": "Electronics",
        "description": "Portable SSDs, routers, mesh kits, chargers, and tech accessories for spec-heavy tasks.",
        "hero_title": "Local demo storage and accessory gear with sharp filters and bundle-like deals.",
    },
    {
        "slug": "appliances",
        "name": "Kitchen & Home Appliances",
        "section": "Home",
        "description": "Coffee makers, air fryers, vacuums, and kitchen upgrades with support coverage options.",
        "hero_title": "Synthetic home upgrades with realistic pricing, pickup options, and plan comparisons.",
    },
    {
        "slug": "phones-wearables",
        "name": "Phones & Wearables",
        "section": "Tech",
        "description": "Phones, watches, and charging gear with delivery and pickup fulfillment demos.",
        "hero_title": "Balance portability, storage, and support plans in a Target-style flow.",
    },
    {
        "slug": "printers-office",
        "name": "Home Office",
        "section": "Office",
        "description": "Printers, label makers, and office helpers with ink, paper, and speed details.",
        "hero_title": "Office setup products with clear specs, easy lookup, and local-only checkout flows.",
    },
]


STORE_DEFS = [
    ("seattle-ballard", "Seattle Ballard", "Seattle", "WA", "1448 NW Market St", "Fast curbside pickup, household essentials, and same-day order lanes."),
    ("bellevue-square", "Bellevue Square", "Bellevue", "WA", "500 Bellevue Way NE", "Target Circle desk, easy pickups, and family shopping support."),
    ("portland-pearl", "Portland Pearl", "Portland", "OR", "910 NW Lovejoy St", "Urban store with compact home, beauty, and kitchen demos."),
    ("san-jose-santana", "San Jose Santana", "San Jose", "CA", "3245 Stevens Creek Blvd", "Tech-forward location with pickup counters and home-office focus."),
    ("los-angeles-culver", "Los Angeles Culver", "Los Angeles", "CA", "10820 Jefferson Blvd", "Extended evening pickup and flexible delivery coverage."),
    ("phoenix-tempe", "Phoenix Tempe", "Tempe", "AZ", "711 S Mill Ave", "Busy college-area store with toy, gaming, and dorm setup selections."),
    ("denver-cherry-creek", "Denver Cherry Creek", "Denver", "CO", "201 Detroit St", "Desk setup, storage, and small-appliance inventory leader."),
    ("austin-domain", "Austin Domain", "Austin", "TX", "11501 Century Oaks Terrace", "Fast shipping handoff and smart-home specialists."),
    ("dallas-plano", "Dallas Plano", "Plano", "TX", "7200 Bishop Rd", "Large pickup zone with kitchen, cleaning, and baby essentials."),
    ("chicago-river-north", "Chicago River North", "Chicago", "IL", "700 N Clark St", "Dense same-day delivery footprint and home-office stock."),
    ("minneapolis-southdale", "Minneapolis Southdale", "Minneapolis", "MN", "165 Southdale Center", "Flagship-style store with broad household assortment."),
    ("atlanta-buckhead", "Atlanta Buckhead", "Atlanta", "GA", "3050 Peachtree Rd NE", "Wearables, beauty, and checkout demo specialists."),
    ("miami-dadeland", "Miami Dadeland", "Miami", "FL", "7535 N Kendall Dr", "High-volume pickup lockers and travel-ready essentials endcaps."),
    ("boston-back-bay", "Boston Back Bay", "Boston", "MA", "799 Boylston St", "Compact city store with support appointment desks."),
    ("new-york-union-square", "New York Union Square", "New York", "NY", "52 E 14th St", "Fast pickup, late hours, and city delivery coverage."),
]


SUPPORT_ARTICLES = [
    ("shipping-delivery-store-pickup", "Shipping, delivery, and store pickup overview", "Shipping & Pickup"),
    ("same-day-delivery-eligibility", "How same-day delivery works in the demo mirror", "Shipping & Pickup"),
    ("curbside-check-in", "Using curbside check-in for synthetic pickup orders", "Shipping & Pickup"),
    ("pickup-id-requirements", "What to bring for demo store pickup", "Shipping & Pickup"),
    ("tracking-synthetic-orders", "Tracking a synthetic order after checkout", "Orders & Tracking"),
    ("order-lookup-by-number", "Finding an order by order number and email", "Orders & Tracking"),
    ("gift-return-demo-policy", "Understanding the local demo return policy", "Returns & Exchanges"),
    ("protection-plan-differences", "Comparing 2-year and 3-year protection plans", "Protection Plans"),
    ("accidental-damage-coverage", "What accidental damage coverage includes", "Protection Plans"),
    ("tv-wall-mount-measuring", "Measure your space before buying a TV", "Buying Guides"),
    ("laptop-memory-storage-guide", "How to compare laptop memory and storage", "Buying Guides"),
    ("camera-lens-kit-guide", "Understanding kit lenses and body-only cameras", "Buying Guides"),
    ("headphone-fit-and-noise-control", "Finding the right fit for headphones and earbuds", "Buying Guides"),
    ("router-mesh-vs-single-unit", "Router vs. mesh: choosing home networking gear", "Buying Guides"),
    ("smart-home-setup-basics", "Getting started with local smart-home setups", "Smart Home"),
    ("target-circle-benefits", "How Target Circle rewards and offers work in the demo mirror", "Rewards"),
    ("target-circle-360-benefits", "Comparing Target Circle and Target Circle 360 benefits", "Rewards"),
    ("same-day-essentials-delivery", "What qualifies for same-day essentials delivery", "Shipping & Pickup"),
    ("appliance-installation-demo", "Installation notes for small appliance purchases", "Appliances"),
    ("monitor-color-workflow", "Choosing a monitor for design and editing", "Computing"),
    ("printer-paper-ink-basics", "Matching printers with the right paper and ink workflow", "Office"),
    ("wearable-cellular-vs-gps", "GPS vs. cellular wearables explained", "Mobile"),
    ("gaming-accessory-compatibility", "Checking gaming accessory compatibility", "Gaming"),
    ("contact-support-options", "Ways to reach demo support in this mirror", "Customer Care"),
]


BENCHMARK_USERS = [
    ("alice.j@test.com", "Alice Jordan", "Seattle", "WA", "bellevue-square", "Target Circle 360"),
    ("bob.c@test.com", "Bob Chen", "Austin", "TX", "austin-domain", "Target Circle"),
    ("carol.d@test.com", "Carol Diaz", "Chicago", "IL", "chicago-river-north", "Target Circle"),
    ("david.k@test.com", "David Kim", "Boston", "MA", "boston-back-bay", "Target Circle"),
]


PRODUCT_TARGETS = {item["slug"]: 13 for item in CATEGORIES}


def _counts_ok() -> bool:
    checks = {
        "users": User.query.count(),
        "categories": Category.query.count(),
        "brands": Brand.query.count(),
        "products": Product.query.count(),
        "stores": Store.query.count(),
        "inventory": StoreInventory.query.count(),
        "reviews": Review.query.count(),
        "orders": Order.query.count(),
    }
    return all(checks[key] >= EXPECTED_COUNTS[key] for key in EXPECTED_COUNTS)


def _write_svg(path: Path, title: str, subtitle: str, palette: tuple[str, str, str], badge: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top, mid, accent = palette
    badge_markup = ""
    if badge:
        badge_markup = (
            f'<rect x="38" y="32" rx="18" ry="18" width="180" height="34" fill="{accent}" opacity="0.95"/>'
            f'<text x="128" y="54" text-anchor="middle" font-size="18" font-family="Arial, Helvetica, sans-serif" font-weight="700" fill="#0c1526">{badge}</text>'
        )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="640" viewBox="0 0 900 640">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{top}" />
    <stop offset="100%" stop-color="{mid}" />
  </linearGradient>
</defs>
<rect width="900" height="640" fill="url(#bg)" />
<circle cx="710" cy="124" r="96" fill="{accent}" opacity="0.18" />
<circle cx="780" cy="180" r="150" fill="#ffffff" opacity="0.05" />
<rect x="40" y="84" width="820" height="500" rx="28" fill="#ffffff" opacity="0.09" />
{badge_markup}
<text x="48" y="142" font-size="22" font-family="Arial, Helvetica, sans-serif" font-weight="700" fill="{accent}">LOCAL BENCHMARK MIRROR</text>
<text x="48" y="248" font-size="54" font-family="Arial, Helvetica, sans-serif" font-weight="800" fill="#ffffff">{title}</text>
<text x="48" y="320" font-size="28" font-family="Arial, Helvetica, sans-serif" fill="#dfe8ff">{subtitle}</text>
<rect x="48" y="372" width="262" height="10" rx="5" fill="{accent}" opacity="0.9" />
<rect x="48" y="405" width="360" height="10" rx="5" fill="#ffffff" opacity="0.35" />
<rect x="48" y="438" width="310" height="10" rx="5" fill="#ffffff" opacity="0.2" />
<rect x="552" y="210" width="258" height="194" rx="26" fill="#ffffff" opacity="0.12" />
<rect x="586" y="244" width="192" height="118" rx="20" fill="{accent}" opacity="0.92" />
<rect x="612" y="275" width="140" height="16" rx="8" fill="#ffffff" opacity="0.9" />
<rect x="612" y="308" width="116" height="16" rx="8" fill="#ffffff" opacity="0.5" />
<rect x="586" y="438" width="168" height="18" rx="9" fill="#ffffff" opacity="0.22" />
<text x="48" y="596" font-size="22" font-family="Arial, Helvetica, sans-serif" fill="#f5f7ff">Generated locally for WebHarbor review only</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def _brand_lookup() -> dict[str, Brand]:
    return {brand.slug: brand for brand in Brand.query.all()}


def _category_lookup() -> dict[str, Category]:
    return {category.slug: category for category in Category.query.all()}


def _add_brand_records() -> None:
    for name, accent in BRANDS:
        db.session.add(Brand(name=name, slug=slugify(name), accent_color=accent))


def _add_category_records(image_root: Path) -> None:
    for category in CATEGORIES:
        palette = CATEGORY_COLORS[category["slug"]]
        relative_path = f"images/categories/{category['slug']}.svg"
        _write_svg(image_root / "categories" / f"{category['slug']}.svg", category["name"], category["hero_title"], palette, "SHOP")
        db.session.add(
            Category(
                name=category["name"],
                slug=category["slug"],
                section=category["section"],
                description=category["description"],
                hero_title=category["hero_title"],
                image_path=relative_path,
            )
        )


def _add_store_records(image_root: Path) -> None:
    amenity_sets = [
        ["Curbside pickup", "Household essentials zone", "Order lockers", "Beauty endcap"],
        ["Curbside pickup", "Order lockers", "Target Circle desk", "Family essentials wall"],
        ["Compact appliance wall", "Seasonal decor zone", "Curbside pickup", "Kitchen feature aisle"],
        ["Home office desk", "Tech accessories wall", "Pickup lockers", "Curbside pickup"],
        ["Living room inspiration bay", "Order lockers", "Curbside pickup", "Delivery desk"],
        ["Toy feature aisle", "Pickup lockers", "Game night endcap", "Dorm essentials wall"],
        ["Desk setup wall", "Printer ink shelf", "Order lockers", "Curbside pickup"],
        ["Smart-home consultation", "Laptop setup desk", "Housewares feature aisle", "Curbside pickup"],
        ["Appliance pickup lane", "Pantry restock wall", "Order lockers", "Protection plan desk"],
        ["Same-day delivery zone", "Cleaning supplies aisle", "Curbside pickup", "Office picks wall"],
        ["Home refresh bay", "Storage solutions wall", "Order lockers", "Curbside pickup"],
        ["Wearables table", "Beauty desk", "Checkout fast lane", "Curbside pickup"],
        ["Travel essentials endcap", "Pickup lockers", "Family tech wall", "Curbside pickup"],
        ["City pickup window", "Appointment support desk", "Order lockers", "Mini home shop"],
        ["Late pickup lane", "School and office wall", "Curbside pickup", "Kitchen basics aisle"],
    ]
    service_sets = [
        ["Same-day pickup window", "Household bundle guidance", "Mobile setup help"],
        ["Accessory setup", "Target Circle help", "Express pickup"],
        ["Kitchen bundle guidance", "Seasonal layout help", "Express pickup"],
        ["Home office setup help", "Accessory matching", "Express pickup"],
        ["TV placement guidance", "Delivery scheduling", "Accessory matching"],
        ["Toy and game matching", "Pickup scheduling", "Express pickup"],
        ["Router setup guidance", "Printer pairing help", "Express pickup"],
        ["Smart-home starter consultation", "Laptop transfer basics", "Delivery scheduling"],
        ["Small appliance guidance", "Rewards help", "Pickup scheduling"],
        ["Printer and paper matching", "Fast lane pickup", "Rewards assistance"],
        ["Room refresh consultation", "Delivery scheduling", "Storage matching"],
        ["Wearable setup help", "Beauty and wellness guidance", "Fast lane pickup"],
        ["Travel charger guidance", "Fast lane pickup", "Rewards assistance"],
        ["Urban pickup scheduling", "Appointment help", "Accessory matching"],
        ["Late-evening pickup", "School and office setup help", "Fast lane pickup"],
    ]
    for index, (slug, name, city, state, address, hero_copy) in enumerate(STORE_DEFS, start=1):
        palette = CATEGORY_COLORS[list(CATEGORY_COLORS.keys())[index % len(CATEGORY_COLORS)]]
        relative_path = f"images/stores/{slug}.svg"
        _write_svg(image_root / "stores" / f"{slug}.svg", name, f"{city}, {state}", palette, "STORE")
        db.session.add(
            Store(
                slug=slug,
                name=name,
                city=city,
                state=state,
                address=address,
                phone=f"(555) 010-{index:04d}"[-14:],
                hours_json=dump_json(
                    [
                        "Mon-Sat: 10:00 AM - 9:00 PM",
                        "Sun: 11:00 AM - 7:00 PM",
                        "Pickup desk opens 30 minutes earlier for reserved orders.",
                    ]
                ),
                amenities_json=dump_json(amenity_sets[index - 1]),
                services_json=dump_json(service_sets[index - 1]),
                hero_copy=hero_copy,
                image_path=relative_path,
            )
        )


def _make_spec_sections(*sections: tuple[str, list[tuple[str, str]]]) -> list[dict[str, object]]:
    return [
        {"title": title, "items": [{"label": label, "value": value} for label, value in items]}
        for title, items in sections
    ]


def _product_payload(
    sku_value: int,
    name: str,
    brand_slug: str,
    category_slug: str,
    price: float,
    list_price: float,
    rating: float,
    review_count: int,
    highlights: list[str],
    specs: list[dict[str, object]],
    tags: list[str],
    description: str,
    long_description: str,
    featured: bool = False,
    deal_badge: str = "",
    pickup_eligible: bool = True,
    delivery_eligible: bool = True,
    stock_count: int = 25,
) -> dict[str, object]:
    return {
        "sku": f"TGT{sku_value}",
        "slug": slugify(f"{name}-{sku_value}"),
        "name": name,
        "brand_slug": brand_slug,
        "category_slug": category_slug,
        "price": round(price, 2),
        "list_price": round(list_price, 2),
        "rating": round(rating, 1),
        "review_count": review_count,
        "highlights": highlights,
        "specs": specs,
        "tags": tags,
        "description": description,
        "long_description": long_description,
        "featured": featured,
        "deal_badge": deal_badge,
        "pickup_eligible": pickup_eligible,
        "delivery_eligible": delivery_eligible,
        "stock_count": stock_count,
    }


def _manual_products() -> list[dict[str, object]]:
    return [
        _product_payload(
            100001,
            'LG Aurora 65" QNED 4K Smart TV',
            "lg",
            "tvs-home-theater",
            1299.99,
            1499.99,
            4.8,
            642,
            ["120Hz panel for sports and gaming", "Filmmaker mode and four HDMI 2.1 ports", "Eligible for same-day delivery in major cities"],
            _make_spec_sections(
                ("Display", [("Screen Size", '65"'), ("Panel Type", "QNED"), ("Resolution", "4K UHD"), ("Refresh Rate", "120Hz")]),
                ("Connectivity", [("HDMI Inputs", "4"), ("Voice Assistant", "Built-in"), ("Wi-Fi", "Wi-Fi 6")]),
            ),
            ["tv", "65 inch", "4k", "qned", "pickup", "delivery"],
            "A bright living-room TV with high refresh and a standout deal badge.",
            "This synthetic flagship TV anchors the local demo home theater selection with store pickup eligibility, delivery options, and clear protection plan choices.",
            featured=True,
            deal_badge="Top Deal",
            stock_count=18,
        ),
        _product_payload(
            100002,
            'Samsung FrameView 55" QLED Art TV',
            "samsung",
            "tvs-home-theater",
            999.99,
            1199.99,
            4.7,
            481,
            ["Art mode gallery rotation", "Slim wall-ready design", "Store pickup available in select metro stores"],
            _make_spec_sections(
                ("Display", [("Screen Size", '55"'), ("Panel Type", "QLED"), ("Resolution", "4K UHD"), ("Refresh Rate", "120Hz")]),
                ("Smart Features", [("Art Mode", "Included"), ("HDR", "HDR10+"), ("Voice Control", "Bixby / Alexa")]),
            ),
            ["tv", "art mode", "qled", "55 inch", "pickup"],
            "A gallery-style TV for shoppers comparing style and specs.",
            "Designed for lifestyle-oriented browsing tasks, this synthetic TV offers a polished product page, vivid store pickup labels, and warranty comparisons.",
            featured=True,
            deal_badge="Member Exclusive",
            stock_count=14,
        ),
        _product_payload(
            100003,
            "Dell Horizon 14 OLED Laptop",
            "dell",
            "laptops",
            1099.99,
            1299.99,
            4.7,
            392,
            ["14-inch OLED touch display", "Intel Core Ultra 7 with 16GB memory", "1TB SSD and Wi-Fi 6E"],
            _make_spec_sections(
                ("Performance", [("Processor", "Intel Core Ultra 7"), ("Memory", "16GB"), ("Storage", "1TB SSD")]),
                ("Display", [("Screen Size", '14"'), ("Panel", "OLED Touch"), ("Battery Life", "15 hours")]),
            ),
            ["laptop", "oled", "1tb", "16gb", "touchscreen"],
            "A premium everyday laptop seeded for compare, search, and checkout tasks.",
            "The Dell Horizon 14 OLED Laptop is a local anchor product with memorable specs, broad inventory coverage, and strong review signals for deterministic tasks.",
            featured=True,
            deal_badge="Save $200",
            stock_count=22,
        ),
        _product_payload(
            100004,
            "Apple MacBook Air 13 Sky M3",
            "apple",
            "laptops",
            1249.99,
            1399.99,
            4.9,
            755,
            ["Fanless M3 design", "13.6-inch Liquid display", "18-hour battery estimate"],
            _make_spec_sections(
                ("Performance", [("Processor", "Apple M3"), ("Memory", "16GB Unified"), ("Storage", "512GB SSD")]),
                ("Design", [("Screen Size", '13.6"'), ("Weight", "2.7 lb"), ("Color", "Sky")]),
            ),
            ["macbook", "apple", "m3", "lightweight", "laptop"],
            "A lightweight benchmark favorite for search-and-compare tasks.",
            "This synthetic MacBook-style laptop is tuned for search, compare, and protection plan tasks in the Target mirror.",
            featured=True,
            deal_badge="Weekend Savings",
            stock_count=19,
        ),
        _product_payload(
            100005,
            "HP EnvyFlex 16 Creator Laptop",
            "hp",
            "laptops",
            1399.99,
            1599.99,
            4.6,
            268,
            ["16-inch color-accurate panel", "Discrete creator graphics", "Pickup today in several stores"],
            _make_spec_sections(
                ("Performance", [("Processor", "Intel Core i9"), ("Memory", "32GB"), ("Storage", "1TB SSD")]),
                ("Display", [("Screen Size", '16"'), ("Panel", "WQXGA"), ("GPU", "RTX 4060")]),
            ),
            ["creator laptop", "32gb", "rtx", "pickup"],
            "Built for editing workflows and task-friendly compare pages.",
            "A synthetic creator laptop with distinctive specs for price, stock, and review-based reasoning tasks.",
            featured=True,
            deal_badge="Open Box Favorite",
            stock_count=9,
        ),
        _product_payload(
            100006,
            "Sony QuietWave XM6 Wireless Headphones",
            "sony",
            "headphones",
            379.99,
            429.99,
            4.8,
            544,
            ["Adaptive noise canceling", "40-hour battery", "Two-device multipoint pairing"],
            _make_spec_sections(
                ("Audio", [("Style", "Over-ear"), ("Battery Life", "40 hours"), ("Noise Canceling", "Adaptive")]),
                ("Connectivity", [("Bluetooth", "5.4"), ("Voice Pickup", "Dual beamforming"), ("Wired Mode", "3.5mm")]),
            ),
            ["headphones", "noise canceling", "wireless", "sony"],
            "A standout audio product with strong support and review signals.",
            "This synthetic flagship headphone model supports tasks around reviews, ratings, delivery, and protection plan comparison.",
            featured=True,
            deal_badge="Top Rated",
            stock_count=27,
        ),
        _product_payload(
            100007,
            "Bose StudioPulse Ultra Earbuds",
            "bose",
            "headphones",
            249.99,
            299.99,
            4.6,
            318,
            ["Compact ANC earbuds", "Wireless charging case", "Clear voice pickup for calls"],
            _make_spec_sections(
                ("Audio", [("Style", "In-ear"), ("Battery Life", "8 hours + case"), ("Noise Canceling", "Hybrid ANC")]),
                ("Comfort", [("Water Resistance", "IPX4"), ("Tips Included", "4 sizes"), ("Wireless Charging", "Yes")]),
            ),
            ["earbuds", "wireless charging", "anc", "bose"],
            "Compact premium earbuds with memorable pricing for budget tasks.",
            "This demo earbud listing complements the flagship over-ear model and gives the support section richer search coverage.",
            featured=True,
            deal_badge="Bundle Bonus",
            stock_count=31,
        ),
        _product_payload(
            100008,
            "Canon Vista R10 Mirrorless Camera Kit",
            "canon",
            "cameras",
            999.99,
            1099.99,
            4.7,
            205,
            ["24.2MP APS-C sensor", "18-45mm starter lens included", "Vertical video guide mode"],
            _make_spec_sections(
                ("Imaging", [("Sensor", "24.2MP APS-C"), ("Lens Included", "18-45mm"), ("Burst Rate", "15 fps")]),
                ("Video", [("4K", "30p oversampled"), ("Stabilization", "Digital + lens"), ("Mic Input", "Yes")]),
            ),
            ["camera", "mirrorless", "canon", "aps-c", "4k"],
            "A seeded mirrorless kit tuned for browse, compare, and pickup tasks.",
            "This local mirrorless kit is ideal for multi-page reasoning involving specs, store availability, and protection plans.",
            featured=True,
            deal_badge="Pickup Today",
            stock_count=11,
        ),
        _product_payload(
            100009,
            "Nikon TrailShot Z5 Body",
            "nikon",
            "cameras",
            1199.99,
            1399.99,
            4.6,
            164,
            ["Full-frame 24MP body", "Weather-sealed design", "IBIS stabilization"],
            _make_spec_sections(
                ("Imaging", [("Sensor", "24MP Full Frame"), ("Body Type", "Mirrorless"), ("Stabilization", "5-axis IBIS")]),
                ("Workflow", [("Card Slots", "Dual SD"), ("Viewfinder", "OLED EVF"), ("USB Power", "Supported")]),
            ),
            ["camera", "nikon", "full frame", "body only"],
            "A body-only camera for deliberate spec comparison tasks.",
            "This seeded camera gives the site a second photography anchor with clear differentiation from kit-based mirrorless options.",
            featured=True,
            deal_badge="Creator Pick",
            stock_count=7,
        ),
        _product_payload(
            100010,
            "Nintendo Switch Neon OLED Bundle",
            "nintendo",
            "gaming",
            399.99,
            449.99,
            4.8,
            701,
            ["7-inch OLED handheld screen", "Dock included", "Bonus carrying sleeve in bundle"],
            _make_spec_sections(
                ("Gaming", [("Screen", '7" OLED'), ("Storage", "64GB"), ("Mode", "Handheld / Docked")]),
                ("Bundle", [("Included", "Carrying sleeve"), ("Controllers", "Neon Joy-Con"), ("Online Trial", "3 months demo")]),
            ),
            ["switch", "oled", "bundle", "gaming console"],
            "A bundle listing with clear value signals for cart and deal tasks.",
            "This product is used for tasks involving bundles, store pickup, and deal detection in gaming search results.",
            featured=True,
            deal_badge="Bundle Deal",
            stock_count=16,
        ),
        _product_payload(
            100011,
            "Microsoft Xbox Carbon Wireless Controller",
            "microsoft",
            "gaming",
            59.99,
            69.99,
            4.7,
            852,
            ["Textured triggers and hybrid D-pad", "Bluetooth + Xbox wireless", "Works with console and PC"],
            _make_spec_sections(
                ("Controls", [("Connection", "Bluetooth / Xbox Wireless"), ("Battery", "AA or rechargeable pack"), ("Color", "Carbon")]),
                ("Compatibility", [("Console", "Xbox Series X|S"), ("PC", "Windows 11"), ("Mobile", "Supported")]),
            ),
            ["controller", "xbox", "gaming accessory", "wireless"],
            "A highly reviewed accessory seeded for price and filter tasks.",
            "This demo controller offers a reliable anchor for search, comparison, and wishlist tasks.",
            featured=True,
            deal_badge="Daily Pick",
            stock_count=48,
        ),
        _product_payload(
            100012,
            "Samsung Tab Slate 11 Plus",
            "samsung",
            "tablets",
            649.99,
            749.99,
            4.5,
            223,
            ["11-inch 120Hz display", "256GB storage", "Pen-ready productivity mode"],
            _make_spec_sections(
                ("Tablet", [("Screen Size", '11"'), ("Storage", "256GB"), ("Battery", "14 hours")]),
                ("Productivity", [("Pen Support", "Included"), ("Keyboard Ready", "Yes"), ("Cellular", "Wi-Fi")]),
            ),
            ["tablet", "11 inch", "samsung", "pen support"],
            "A mid-premium tablet with clear productivity positioning.",
            "Great for support article tasks about delivery, tablets, and accessory compatibility.",
            featured=True,
            deal_badge="Online Only",
            stock_count=15,
        ),
        _product_payload(
            100013,
            "Logitech PowerGrid Mechanical Keyboard",
            "logitech",
            "gaming",
            129.99,
            149.99,
            4.6,
            287,
            ["Wireless tri-mode connection", "Per-key lighting", "Low-profile tactile switches"],
            _make_spec_sections(
                ("Keyboard", [("Connection", "Bluetooth / USB / 2.4GHz"), ("Switch Type", "Tactile"), ("Battery", "30 hours with RGB")]),
                ("Build", [("Layout", "TKL"), ("Weight", "1.9 lb"), ("Palm Rest", "Optional")]),
            ),
            ["keyboard", "mechanical", "gaming", "wireless"],
            "A gaming keyboard tuned for cart, compare, and support coverage tasks.",
            "This seeded keyboard gives the gaming category a high-intent accessory with memorable specifications.",
            featured=True,
            deal_badge="Member Price",
            stock_count=24,
        ),
        _product_payload(
            100014,
            'TCL CinemaCore 75" Mini-LED TV',
            "tcl",
            "tvs-home-theater",
            1499.99,
            1799.99,
            4.5,
            198,
            ["75-inch mini-LED panel", "240 motion rate", "Game accelerator mode"],
            _make_spec_sections(
                ("Display", [("Screen Size", '75"'), ("Panel Type", "Mini-LED"), ("Resolution", "4K UHD"), ("Refresh Rate", "144Hz VRR")]),
                ("Gaming", [("VRR", "Yes"), ("ALLM", "Yes"), ("Audio", "2.1 channel speakers")]),
            ),
            ["tv", "75 inch", "mini-led", "gaming tv"],
            "A large-format TV seeded for high-price comparison tasks.",
            "This TV gives the home theater catalog a second large-screen anchor with a different panel story and price tier.",
            featured=True,
            deal_badge="Big Screen Event",
            stock_count=8,
        ),
        _product_payload(
            100015,
            "Acer NitroMesh 27 Gaming Monitor",
            "acer",
            "monitors",
            329.99,
            399.99,
            4.7,
            376,
            ["27-inch QHD IPS panel", "180Hz refresh", "Height-adjustable stand"],
            _make_spec_sections(
                ("Display", [("Size", '27"'), ("Resolution", "2560 x 1440"), ("Refresh Rate", "180Hz"), ("Panel", "IPS")]),
                ("Gaming", [("Response Time", "1ms"), ("Sync", "FreeSync Premium"), ("Inputs", "HDMI x2 / DP")]),
            ),
            ["monitor", "gaming", "27 inch", "qhd", "180hz"],
            "A memorable gaming display with strong compare-page differentiation.",
            "This seeded monitor helps with filter-based tasks for refresh rate, price, and pickup availability.",
            featured=True,
            deal_badge="Hot Offer",
            stock_count=17,
        ),
        _product_payload(
            100016,
            "Apple Watch Tide 44mm GPS",
            "apple",
            "phones-wearables",
            379.99,
            429.99,
            4.8,
            631,
            ["44mm aluminum case", "Sleep and activity tracking", "Fast charging"],
            _make_spec_sections(
                ("Wearable", [("Case Size", "44mm"), ("Connectivity", "GPS"), ("Battery", "18 hours")]),
                ("Health", [("Heart Rate", "Yes"), ("Water Resistance", "50m"), ("Crash Detection", "Included")]),
            ),
            ["watch", "apple", "gps", "wearable"],
            "A recognizable wearable for rewards and support tasks.",
            "This watch offers a clean path for store pickup, delivery options, and support article tasks around wearable connectivity.",
            featured=True,
            deal_badge="Popular Pickup",
            stock_count=21,
        ),
        _product_payload(
            100017,
            "Dyson PureBreeze Cool Tower",
            "dyson",
            "appliances",
            499.99,
            549.99,
            4.4,
            142,
            ["Purifies and cools", "Remote with night mode", "Oscillation and auto mode"],
            _make_spec_sections(
                ("Air Care", [("Modes", "Cool / Purify"), ("Oscillation", "350 degrees"), ("Filter", "HEPA + carbon")]),
                ("Convenience", [("Noise", "Quiet mode"), ("Control", "Remote"), ("Footprint", "Slim tower")]),
            ),
            ["air purifier", "tower fan", "dyson"],
            "An appliance seed product designed for delivery and plan-comparison tasks.",
            "This demo appliance introduces a higher-ticket home item with thoughtful delivery, support, and protection plan angles.",
            featured=True,
            deal_badge="Healthy Home",
            stock_count=6,
        ),
        _product_payload(
            100018,
            "WD Vault 2TB Portable SSD",
            "wd",
            "storage-networking",
            169.99,
            199.99,
            4.7,
            412,
            ["USB-C portable SSD", "2TB capacity", "Drop-resistant shell"],
            _make_spec_sections(
                ("Storage", [("Capacity", "2TB"), ("Connection", "USB-C 10Gbps"), ("Read Speed", "1,050 MB/s")]),
                ("Travel", [("Weight", "0.19 lb"), ("Resistance", "Drop resistant"), ("Cable Included", "USB-C / USB-A")]),
            ),
            ["ssd", "2tb", "portable", "wd"],
            "A benchmark-friendly storage product with clear capacity and speed filters.",
            "This seeded portable SSD supports tasks around cheapest eligible products, deals, and office/creator shopping flows.",
            featured=True,
            deal_badge="Fast Storage",
            stock_count=33,
        ),
        _product_payload(
            100019,
            "Belkin Boost 3-in-1 Mag Stand",
            "belkin",
            "phones-wearables",
            129.99,
            149.99,
            4.5,
            217,
            ["Phone, watch, and earbud charging", "Weighted desk base", "Travel-friendly cord wrap"],
            _make_spec_sections(
                ("Charging", [("Outputs", "3 devices"), ("Phone Alignment", "Magnetic"), ("Cable", "USB-C included")]),
                ("Design", [("Finish", "Soft-touch"), ("Travel", "Cord wrap"), ("Footprint", "Compact stand")]),
            ),
            ["charger", "belkin", "magnetic", "3-in-1"],
            "A small accessory with high-intent shopper signals and plan upsell space.",
            "This charging stand gives the mobile category a compact accessory for search, cart, and protection plan tasks.",
            featured=True,
            deal_badge="Desk Setup Pick",
            stock_count=26,
        ),
        _product_payload(
            100020,
            "Insignia Dual Brew 12-Cup Coffee Station",
            "insignia",
            "appliances",
            89.99,
            109.99,
            4.3,
            188,
            ["Brew pot or single cup", "Programmable timer", "Removable water reservoir"],
            _make_spec_sections(
                ("Brewing", [("Capacity", "12 cups"), ("Single Serve", "Yes"), ("Timer", "24-hour programmable")]),
                ("Maintenance", [("Reservoir", "Removable"), ("Carafe", "Glass"), ("Footprint", "Counter friendly")]),
            ),
            ["coffee maker", "dual brew", "insignia"],
            "An accessible appliance for deal, support, and checkout tasks.",
            "This synthetic coffee station rounds out the appliance selection with a lower price point and strong support article relevance.",
            featured=True,
            deal_badge="Kitchen Refresh",
            stock_count=28,
        ),
    ]


def _generic_products(start_sku: int) -> list[dict[str, object]]:
    payloads = _manual_products()
    counts = {slug: 0 for slug in PRODUCT_TARGETS}
    brand_display = {slugify(name): name for name, _ in BRANDS}
    for payload in payloads:
        counts[payload["category_slug"]] += 1

    sku_value = start_sku
    brand_sets = {
        "laptops": ["dell", "hp", "lenovo", "asus", "acer", "apple", "microsoft", "samsung", "lg"],
        "tvs-home-theater": ["samsung", "lg", "sony", "tcl", "insignia", "epson"],
        "tablets": ["apple", "samsung", "lenovo", "microsoft", "acer"],
        "cameras": ["canon", "nikon", "sony", "gopro", "samsung"],
        "headphones": ["sony", "bose", "jbl", "apple", "logitech", "samsung"],
        "gaming": ["nintendo", "microsoft", "sony", "logitech", "acer", "asus"],
        "smart-home": ["samsung", "belkin", "insignia", "apple", "sony"],
        "monitors": ["acer", "lg", "dell", "asus", "samsung", "hp"],
        "storage-networking": ["wd", "belkin", "logitech", "samsung", "epson", "brother"],
        "appliances": ["dyson", "insignia", "lg", "samsung", "hp", "belkin"],
        "phones-wearables": ["apple", "samsung", "belkin", "garmin", "sony"],
        "printers-office": ["hp", "canon", "epson", "brother", "dell"],
    }
    series_names = {
        "laptops": ["FlexBook", "CreatorEdge", "CampusPro", "PixelLine", "TravelLite", "StudioNorth"],
        "tvs-home-theater": ["VisionCore", "BrightRoom", "MovieNight", "StudioScreen", "ArenaView"],
        "tablets": ["NoteSlate", "CampusTab", "SketchPad", "ViewMate"],
        "cameras": ["TravelSnap", "SceneCraft", "VlogReady", "ActionTrail"],
        "headphones": ["SoundArc", "QuietLine", "PulseOne", "CityTune"],
        "gaming": ["ArenaPack", "PlayCore", "Respawn", "LevelShift"],
        "smart-home": ["HomeGrid", "GlowDock", "SafeView", "ComfortHub"],
        "monitors": ["PixelDeck", "StudioCanvas", "SwiftFrame", "ArenaPanel"],
        "storage-networking": ["VaultLine", "MeshPort", "StreamNode", "SpeedStore"],
        "appliances": ["KitchenFlow", "FreshAir", "QuickHeat", "BlendMate"],
        "phones-wearables": ["PocketLink", "TrackPulse", "MagCharge", "MotionFit"],
        "printers-office": ["OfficeJet", "PaperFlow", "ScanSmart", "LabelShift"],
    }
    spec_labels = {
        "laptops": [
            ("Processor", ["Intel Core i5", "Intel Core i7", "AMD Ryzen 7", "Intel Core Ultra 7"]),
            ("Memory", ["16GB", "16GB", "24GB", "32GB"]),
            ("Storage", ["512GB SSD", "1TB SSD", "1TB SSD", "2TB SSD"]),
            ("Screen Size", ['13.3"', '14"', '15.6"', '16"']),
        ],
        "tvs-home-theater": [
            ("Screen Size", ['50"', '55"', '65"', '75"']),
            ("Panel Type", ["LED", "QLED", "OLED", "Mini-LED"]),
            ("Resolution", ["4K UHD", "4K UHD", "4K UHD", "8K Demo"]),
            ("Refresh Rate", ["60Hz", "120Hz", "120Hz", "144Hz"]),
        ],
        "tablets": [
            ("Screen Size", ['10.9"', '11"', '12.4"', '12.9"']),
            ("Storage", ["128GB", "256GB", "256GB", "512GB"]),
            ("Battery", ["12 hours", "13 hours", "14 hours", "15 hours"]),
            ("Connectivity", ["Wi-Fi", "Wi-Fi", "Wi-Fi + 5G", "Wi-Fi + 5G"]),
        ],
        "cameras": [
            ("Sensor", ["24MP APS-C", "32MP APS-C", "24MP Full Frame", "5.3K Action Sensor"]),
            ("Lens Included", ["Body Only", "18-45mm Kit", "16-50mm Kit", "Zoom Module"]),
            ("Video", ["4K30", "4K60", "6K Open Gate", "5.3K60"]),
            ("Stabilization", ["Digital", "Lens + Digital", "5-axis IBIS", "HyperSmooth"]),
        ],
        "headphones": [
            ("Style", ["Over-ear", "On-ear", "In-ear", "Open-ear"]),
            ("Battery Life", ["8 hours", "20 hours", "30 hours", "40 hours"]),
            ("Noise Canceling", ["Passive", "Hybrid ANC", "Adaptive ANC", "Adaptive ANC"]),
            ("Connection", ["Bluetooth 5.3", "Bluetooth 5.4", "Bluetooth + USB-C", "Bluetooth"]),
        ],
        "gaming": [
            ("Platform", ["Xbox / PC", "Switch", "PlayStation / PC", "Universal"]),
            ("Connection", ["Wireless", "Wireless", "USB-C", "Bluetooth / USB"]),
            ("Battery", ["Rechargeable", "Rechargeable", "AA or pack", "No battery"]),
            ("Feature", ["RGB", "Motion control", "Hall effect sticks", "Low latency mode"]),
        ],
        "smart-home": [
            ("Category", ["Thermostat", "Security Cam", "Smart Speaker", "Lighting Hub"]),
            ("Connectivity", ["Wi-Fi", "Wi-Fi 6", "Matter", "Thread"]),
            ("Control", ["Voice + app", "App", "Voice + touch", "App + automation"]),
            ("Power", ["Battery", "Plug-in", "Battery or wired", "USB-C"]),
        ],
        "monitors": [
            ("Size", ['24"', '27"', '32"', '34"']),
            ("Resolution", ["1080p", "QHD", "4K UHD", "UWQHD"]),
            ("Refresh Rate", ["75Hz", "144Hz", "165Hz", "240Hz"]),
            ("Panel", ["IPS", "VA", "OLED", "IPS Black"]),
        ],
        "storage-networking": [
            ("Type", ["Portable SSD", "Mesh Router", "Memory Card", "NAS Drive"]),
            ("Capacity", ["1TB", "2TB", "512GB", "4TB"]),
            ("Connection", ["USB-C", "Wi-Fi 6", "UHS-II", "2.5GbE"]),
            ("Speed", ["1,050 MB/s", "3.6 Gbps", "300 MB/s", "5400 RPM"]),
        ],
        "appliances": [
            ("Category", ["Air Fryer", "Coffee Maker", "Blender", "Air Purifier"]),
            ("Capacity", ["4 qt", "12 cups", "68 oz", "350 sq ft"]),
            ("Power", ["1500W", "1200W", "1100W", "Quiet mode"]),
            ("Controls", ["Digital", "Programmable", "Preset programs", "Remote"]),
        ],
        "phones-wearables": [
            ("Type", ["Phone", "Watch", "Charger", "Tracker"]),
            ("Storage", ["128GB", "256GB", "N/A", "N/A"]),
            ("Battery", ["All-day", "18 hours", "Fast charge", "7 days"]),
            ("Connectivity", ["5G", "GPS", "Magnetic", "Bluetooth"]),
        ],
        "printers-office": [
            ("Type", ["All-in-One", "Photo Printer", "Label Maker", "Document Scanner"]),
            ("Speed", ["11 ppm", "22 ppm", "N/A", "40 ppm"]),
            ("Connection", ["Wi-Fi", "Wi-Fi + USB", "Bluetooth", "USB-C"]),
            ("Media", ["Plain + glossy", "Photo paper", "Thermal label", "ADF 50 sheets"]),
        ],
    }

    descriptions = {
        "laptops": "A local demo laptop with clear specs, realistic pricing, and checkout-safe inventory.",
        "tvs-home-theater": "A synthetic TV or theater product with strong deal, review, and delivery metadata.",
        "tablets": "A tablet-oriented product seeded for filter, compare, and accessory-friendly tasks.",
        "cameras": "A camera listing with pickup-ready stock and structured specs for search and compare tasks.",
        "headphones": "An audio item designed for ratings, delivery, and protection plan reasoning.",
        "gaming": "A gaming-focused product with memorable keywords, compare value, and pickup eligibility.",
        "smart-home": "A connected-home product that pairs naturally with support article workflows.",
        "monitors": "A display-focused listing with size, panel, and refresh information front and center.",
        "storage-networking": "A storage or networking product with clean capacity and speed comparisons.",
        "appliances": "A small appliance listing with support coverage, pickup options, and warranty hooks.",
        "phones-wearables": "A mobile or wearable product with accessory, support, and checkout-friendly metadata.",
        "printers-office": "An office product with crisp specs and support ties for shipping and setup questions.",
    }

    while any(counts[slug] < PRODUCT_TARGETS[slug] for slug in PRODUCT_TARGETS):
        for category_slug, target in PRODUCT_TARGETS.items():
            if counts[category_slug] >= target:
                continue
            index = counts[category_slug]
            brand_slug = brand_sets[category_slug][index % len(brand_sets[category_slug])]
            spec_source = spec_labels[category_slug]
            values = [choices[index % len(choices)] for _, choices in spec_source]
            series = series_names[category_slug][index % len(series_names[category_slug])]
            name = f"{brand_display[brand_slug]} {series} {index + 1}"
            if category_slug == "laptops":
                name += " Laptop"
            elif category_slug == "tvs-home-theater":
                name += " TV"
            elif category_slug == "monitors":
                name += " Monitor"
            elif category_slug == "headphones":
                name += " Headphones"
            elif category_slug == "cameras":
                name += " Camera"
            elif category_slug == "tablets":
                name += " Tablet"
            elif category_slug == "storage-networking":
                name += " Kit"
            elif category_slug == "printers-office":
                name += " System"

            price = 79.99 + (index * 57) + (list(PRODUCT_TARGETS).index(category_slug) * 38)
            if category_slug in {"laptops", "tvs-home-theater", "cameras"}:
                price += 380
            if category_slug == "phones-wearables":
                price += 120
            list_price = price + 40 + (index % 4) * 25
            rating = 4.1 + ((index + len(category_slug)) % 7) * 0.1
            review_count = 60 + index * 19 + len(category_slug)
            specs = _make_spec_sections(
                ("Highlights", list(zip([label for label, _ in spec_source], values))),
                ("Why it stands out", [("Pickup", "Eligible" if index % 3 != 0 else "Ship to home"), ("Delivery", "2-day demo" if index % 4 != 0 else "Same-day demo"), ("Protection", "2 and 3-year plans")]),
            )
            payloads.append(
                _product_payload(
                    sku_value,
                    name,
                    brand_slug,
                    category_slug,
                    price,
                    list_price,
                    rating,
                    review_count,
                    [
                        f"{values[0]} tuned for {category_slug.replace('-', ' ')} shoppers",
                        "Synthetic stock and pickup labels for benchmark reliability",
                        "Protection plans and support articles linked from the detail page",
                    ],
                    specs,
                    [category_slug, brand_slug, series.lower(), values[0].lower()],
                    descriptions[category_slug],
                    descriptions[category_slug] + " The compare page uses the same specs so multi-step tasks stay grounded.",
                    featured=index < 2,
                    deal_badge="Deal of the Day" if index % 5 == 0 else "",
                    pickup_eligible=index % 3 != 0,
                    delivery_eligible=index % 4 != 0,
                    stock_count=8 + ((index * 3) % 35),
                )
            )
            counts[category_slug] += 1
            sku_value += 1
    return payloads


def _ensure_generated_assets(image_root: Path) -> None:
    for category in Category.query.all():
        _write_svg(
            image_root / "categories" / f"{category.slug}.svg",
            category.name,
            category.hero_title,
            CATEGORY_COLORS[category.slug],
            "SHOP",
        )
    for store in Store.query.all():
        palette = CATEGORY_COLORS[list(CATEGORY_COLORS.keys())[store.id % len(CATEGORY_COLORS)]]
        _write_svg(
            image_root / "stores" / f"{store.slug}.svg",
            store.name,
            f"{store.city}, {store.state}",
            palette,
            "STORE",
        )
    for product in Product.query.all():
        _write_svg(
            image_root / "products" / f"{product.sku}.svg",
            product.name,
            product.brand.name,
            CATEGORY_COLORS[product.category.slug],
            product.deal_badge or product.category.name,
        )
    _attach_seed_images(image_root)


def _persist_products(image_root: Path) -> list[Product]:
    brand_lookup = _brand_lookup()
    category_lookup = _category_lookup()
    products: list[Product] = []
    for payload in _generic_products(100021):
        brand = brand_lookup[payload["brand_slug"]]
        category = category_lookup[payload["category_slug"]]
        palette = CATEGORY_COLORS[category.slug]
        relative_path = f"images/products/{payload['sku']}.svg"
        _write_svg(image_root / "products" / f"{payload['sku']}.svg", payload["name"], brand.name, palette, payload["deal_badge"] or category.name)
        product = Product(
            sku=payload["sku"],
            slug=payload["slug"],
            name=payload["name"],
            short_description=payload["description"],
            long_description=payload["long_description"],
            price=payload["price"],
            list_price=payload["list_price"],
            rating=payload["rating"],
            review_count=payload["review_count"],
            availability_status="In stock" if payload["stock_count"] > 6 else "Limited stock",
            pickup_eligible=payload["pickup_eligible"],
            delivery_eligible=payload["delivery_eligible"],
            featured=payload["featured"],
            deal_badge=payload["deal_badge"],
            image_path=relative_path,
            highlights_json=dump_json(payload["highlights"]),
            specs_json=dump_json(payload["specs"]),
            tags_json=dump_json(payload["tags"]),
            search_keywords=" ".join(payload["tags"] + [brand.name.lower(), category.name.lower()]),
            stock_count=payload["stock_count"],
            category_id=category.id,
            brand_id=brand.id,
        )
        db.session.add(product)
        products.append(product)
    db.session.flush()
    return products


def _add_delivery_options() -> None:
    options = [
        ("standard-shipping", "Standard delivery", "Arrives in 3-5 business days", 0.0, "Arrives by Thu, Mar 26"),
        ("expedited-shipping", "Expedited delivery", "Faster delivery for urgent orders", 14.99, "Arrives by Tue, Mar 24"),
        ("scheduled-delivery", "Scheduled delivery", "Choose a preferred delivery day for large items", 24.99, "Select a 2-hour delivery window"),
    ]
    for slug, title, description, fee, eta in options:
        db.session.add(DeliveryOption(slug=slug, title=title, description=description, fee=fee, eta_label=eta))


def _add_pickup_slots() -> None:
    for store in Store.query.all():
        for offset, window in enumerate(["10:00 AM - 12:00 PM", "1:00 PM - 3:00 PM", "5:00 PM - 7:00 PM"]):
            db.session.add(
                PickupSlot(
                    store_id=store.id,
                    slot_code=f"{store.slug}-{offset}",
                    day_label=(SEED_TIMESTAMP + timedelta(days=offset + 1)).strftime("%a, %b %d"),
                    time_window=window,
                    available_capacity=12 - offset * 2,
                )
            )


def _add_store_inventory(products: list[Product]) -> None:
    stores = Store.query.order_by(Store.id.asc()).all()
    for product in products:
        for store in stores:
            marker = (product.id * 7 + store.id * 3) % 5
            if marker == 0 and product.id % 4 != 0:
                continue
            quantity = 2 + ((product.id + store.id) % 16)
            pickup_window = "Ready in 1 hour" if quantity > 10 else "Ready today"
            db.session.add(
                StoreInventory(
                    store_id=store.id,
                    product_id=product.id,
                    quantity=quantity,
                    pickup_window=pickup_window,
                    aisle=f"{chr(65 + (store.id % 5))}-{(product.id % 12) + 1}",
                )
            )


def _add_reviews(products: list[Product]) -> None:
    reviewer_names = ["Maya", "Jordan", "Chris", "Taylor", "Sam", "Riley", "Alex", "Morgan"]
    review_titles = [
        "Worth the upgrade",
        "Easy local pickup",
        "Great value in the demo catalog",
        "Specs matched what I needed",
        "Would recommend after comparing a few options",
        "Support article made setup simple",
    ]
    for product in products:
        review_total = 3 if product.featured else 2
        for index in range(review_total):
            rating = min(5, max(3, int(round(product.rating + (index % 2) - 0.5))))
            db.session.add(
                Review(
                    product_id=product.id,
                    author_name=reviewer_names[(product.id + index) % len(reviewer_names)],
                    title=review_titles[(product.id + index) % len(review_titles)],
                    body=(
                        f"This synthetic review mentions {product.name}, store pickup, and the local support flow. "
                        f"It is designed to ground review and rating tasks for {product.category.name.lower()}."
                    ),
                    rating=rating,
                    verified=index % 2 == 0,
                    created_at=SEED_TIMESTAMP - timedelta(days=(product.id + index) % 45),
                )
            )


def _add_protection_plans(products: list[Product]) -> None:
    for product in products:
        price = round(max(19.99, product.price * 0.11), 2)
        db.session.add(
            ProtectionPlan(
                product_id=product.id,
                name=f"2-Year Protection for {product.name}",
                years=2,
                price=price,
                coverage_summary="Covers power issues, mechanical failure, and support routing.",
                accidental=False,
                priority_support=True,
            )
        )
        db.session.add(
            ProtectionPlan(
                product_id=product.id,
                name=f"3-Year Accidental Plan for {product.name}",
                years=3,
                price=round(price * 1.45, 2),
                coverage_summary="Adds accidental handling coverage and priority replacement review.",
                accidental=True,
                priority_support=True,
            )
        )


def _add_support_articles() -> None:
    article_bodies = {
        "shipping-delivery-store-pickup": "Standard demo delivery arrives in 3-5 business days. Same-day delivery appears only in selected metro areas. Store pickup orders show a pickup window on the order detail page.",
        "same-day-delivery-eligibility": "Same-day delivery is available only for items marked as delivery eligible and only in stores covering that synthetic ZIP area. Large items may fall back to scheduled delivery.",
        "curbside-check-in": "Use the synthetic store name, order number, and the pickup window shown in the order page. The mirror does not require a real phone number to simulate check-in.",
        "pickup-id-requirements": "For demo pickup, bring the synthetic order number and a photo ID listed on the benchmark account. Another person can collect only if the order note says alternate pickup is enabled.",
        "tracking-synthetic-orders": "After checkout, the order page shows whether the order is preparing shipment, shipped, delivered, or ready for pickup. No real carrier tracking exists in this mirror.",
        "order-lookup-by-number": "Order lookup requires a synthetic order number plus the seeded email used on that order. Successful lookup stores a local session so the detail page can be refreshed.",
        "gift-return-demo-policy": "Demo returns are informational only. Orders are not really canceled or refunded, but the mirror explains the policy language and steps a shopper would usually follow.",
        "protection-plan-differences": "Two-year plans focus on mechanical and power issues. Three-year accidental plans add handling damage coverage and priority replacement review.",
        "accidental-damage-coverage": "Accidental plans cover drops, spills, and cracked surfaces for eligible devices. Basic plans do not include accidental handling.",
        "tv-wall-mount-measuring": "Measure the width of the wall, note viewing distance, and confirm VESA compatibility before choosing a mount. Large-screen delivery may suggest scheduled slots.",
        "laptop-memory-storage-guide": "Memory affects multitasking while storage affects local file capacity. Creator and gaming models in this mirror highlight 16GB, 24GB, and 32GB options plus 512GB to 2TB SSD tiers.",
        "camera-lens-kit-guide": "Kit lenses are more flexible for first-time buyers, while body-only listings work better if you already own compatible lenses.",
        "headphone-fit-and-noise-control": "Over-ear models prioritize long battery life and strong passive isolation. Earbuds focus on portability and case charging.",
        "router-mesh-vs-single-unit": "Mesh kits help larger homes while single routers fit smaller apartments. The mirror includes both so tasks can compare capacity and speed.",
        "smart-home-setup-basics": "Use the product detail page to check Wi-Fi, Matter, or Thread support before choosing hubs, cameras, and speakers.",
        "target-circle-benefits": "Target Circle points and offers in this mirror come from seeded orders and promotions. The dashboard can also reflect certificate-style savings redemptions.",
        "target-circle-360-benefits": "Target Circle 360 adds richer delivery messaging, extra support copy, and membership-style perks in this local mirror.",
        "same-day-essentials-delivery": "Everyday items marked with delivery badges can use same-day essentials delivery in supported metro stores. No real courier network is contacted.",
        "appliance-installation-demo": "Small appliances use simple delivery messaging. This site does not schedule real installation or technician appointments.",
        "monitor-color-workflow": "Creators should compare panel type, color-focused terminology, and resolution together, not refresh rate alone.",
        "printer-paper-ink-basics": "Pair photo printers with glossy media and office models with high-yield ink workflows. Support tasks use these distinctions heavily.",
        "wearable-cellular-vs-gps": "GPS models sync with a phone, while cellular-capable wearables can receive more independent notifications and location features.",
        "gaming-accessory-compatibility": "Check the platform field on the product detail page before adding controllers, keyboards, and headsets to the cart.",
        "contact-support-options": "This local mirror offers synthetic chat, email, and phone support history through seeded support tickets. No live agents are contacted.",
    }
    for index, (slug, title, topic) in enumerate(SUPPORT_ARTICLES, start=1):
        body = (
            f"{article_bodies.get(slug, title)}\n"
            "No real shipment, order placement, or external service is involved.\n"
            "Use the surrounding UI to complete grounded support, pickup, delivery, and rewards tasks."
        )
        db.session.add(
            SupportArticle(
                slug=slug,
                title=title,
                topic=topic,
                summary=f"Demo guidance for {topic.lower()} tasks.",
                body=body,
                upstream_url="https://www.target.com/c/store-pickup/-/N-5xsxt",
                keywords_json=dump_json([topic.lower(), "target demo", slug.replace("-", " ")]),
            )
        )


def _add_deals(products: list[Product]) -> None:
    sorted_products = sorted(products, key=lambda product: product.discount_percent(), reverse=True)
    for index, product in enumerate(sorted_products[:18], start=1):
        db.session.add(
            Deal(
                slug=f"deal-{product.sku.lower()}",
                title=f"{product.name} limited-time savings",
                subtitle=f"Save {product.discount_percent()}% on a local demo favorite.",
                badge="Top Deal" if index <= 6 else "Member Deal",
                discount_percent=product.discount_percent(),
                ends_label=f"Ends {['Mar 28', 'Mar 29', 'Mar 30'][index % 3]}",
                category_slug=product.category.slug,
                product_id=product.id,
            )
        )


def _add_users_and_accounts() -> list[User]:
    created_users: list[User] = []
    for index, (email, full_name, city, state, preferred_store_slug, tier) in enumerate(BENCHMARK_USERS, start=1):
        user = User(
            email=email,
            full_name=full_name,
            phone=f"555-100-{index:04d}"[-12:],
            city=city,
            state=state,
            preferred_store_slug=preferred_store_slug,
            member_tier=tier,
            rewards_member_id=f"TGC-{420000 + index}",
            created_at=SEED_TIMESTAMP - timedelta(days=120 - index * 5),
        )
        user.set_password(BENCHMARK_PASSWORD)
        db.session.add(user)
        db.session.flush()
        db.session.add(
            RewardAccount(
                user_id=user.id,
                member_id=user.rewards_member_id,
                points_balance=1600 + index * 240,
                tier=tier,
                available_certificates=index - 1,
            )
        )
        created_users.append(user)
    return created_users


def _add_reward_activity(users: list[User]) -> None:
    for user_index, user in enumerate(users, start=1):
        for activity_index in range(5):
            delta = [140, 260, -50, 320, 90][activity_index]
            db.session.add(
                RewardActivity(
                    user_id=user.id,
                    points_delta=delta,
                    title=[
                        "Home order points",
                        "Weekly deal bonus",
                        "Offer redemption",
                        "Store pickup promo",
                        "Target Circle appreciation credit",
                    ][activity_index],
                    note="Synthetic rewards activity used for account dashboard tasks.",
                    created_at=SEED_TIMESTAMP - timedelta(days=user_index * 10 + activity_index * 6),
                )
            )


def _add_support_tickets(users: list[User]) -> None:
    for index, user in enumerate(users, start=1):
        db.session.add(
            SupportTicket(
                user_id=user.id,
                subject=f"Pickup window confirmation for order TGT-24{index:04d}",
                status="Resolved" if index % 2 else "Awaiting follow-up",
                channel="Chat" if index % 2 else "Email",
                summary="Synthetic support history entry for dashboard review tasks.",
                created_at=SEED_TIMESTAMP - timedelta(days=14 + index * 4),
            )
        )
        db.session.add(
            SupportTicket(
                user_id=user.id,
                subject=f"Protection plan question for demo household bundle #{index}",
                status="Resolved",
                channel="Phone",
                summary="Synthetic support note about protection plan comparison.",
                created_at=SEED_TIMESTAMP - timedelta(days=25 + index * 5),
            )
        )


def _add_wishlist_compare_cart(users: list[User], products: list[Product]) -> None:
    for user_index, user in enumerate(users):
        picks = products[user_index * 8 : user_index * 8 + 8]
        for product in picks[:4]:
            db.session.add(WishlistItem(user_id=user.id, product_id=product.id))
        for product in picks[4:7]:
            db.session.add(CompareItem(user_id=user.id, product_id=product.id))

        first_product = picks[0]
        plan = ProtectionPlan.query.filter_by(product_id=first_product.id).order_by(ProtectionPlan.price.asc()).first()
        delivery_option = DeliveryOption.query.filter_by(slug="standard-shipping").first()
        db.session.add(
            CartItem(
                user_id=user.id,
                product_id=first_product.id,
                quantity=1 + (user_index % 2),
                fulfillment_method="delivery",
                delivery_option_id=delivery_option.id if delivery_option else None,
                protection_plan_id=plan.id if plan else None,
                created_at=SEED_TIMESTAMP - timedelta(days=1 + user_index),
            )
        )

        second_product = picks[1]
        pickup_store = Store.query.filter_by(slug=user.preferred_store_slug).first()
        db.session.add(
            CartItem(
                user_id=user.id,
                product_id=second_product.id,
                quantity=1,
                fulfillment_method="pickup",
                store_id=pickup_store.id if pickup_store else None,
                created_at=SEED_TIMESTAMP - timedelta(hours=6 + user_index),
            )
        )


def _seed_orders(users: list[User], products: list[Product]) -> None:
    delivery_options = DeliveryOption.query.order_by(DeliveryOption.id.asc()).all()
    stores = Store.query.order_by(Store.id.asc()).all()
    order_counter = 0

    for user_index, user in enumerate(users, start=1):
        for local_index in range(15):
            order_counter += 1
            status_cycle = ["Delivered", "Delivered", "Shipped", "Ready for pickup", "Processing"]
            mode = "pickup" if local_index % 4 == 0 else "delivery"
            store = stores[(user_index + local_index) % len(stores)] if mode == "pickup" else None
            delivery_option = delivery_options[(user_index + local_index) % len(delivery_options)] if mode == "delivery" else None
            base_product = products[(user_index * 17 + local_index * 3) % len(products)]
            extra_product = products[(user_index * 19 + local_index * 5 + 11) % len(products)]
            subtotal = round(base_product.price + (extra_product.price if local_index % 3 == 0 else 0), 2)
            shipping_fee = delivery_option.fee if delivery_option else 0.0
            tax = round((subtotal + shipping_fee) * 0.086, 2)
            total = round(subtotal + shipping_fee + tax, 2)
            order = Order(
                user_id=user.id,
                order_number=f"TGT-{240000 + order_counter}",
                email=user.email,
                status=status_cycle[local_index % len(status_cycle)],
                subtotal=subtotal,
                tax=tax,
                total=total,
                fulfillment_method=mode,
                store_id=store.id if store else None,
                delivery_option_id=delivery_option.id if delivery_option else None,
                shipping_name=user.full_name,
                shipping_city=user.city,
                shipping_state=user.state,
                shipping_zip=f"98{user_index}{local_index:03d}"[-5:],
                payment_brand="Demo Visa" if local_index % 2 == 0 else "Demo Mastercard",
                payment_last4=f"{1111 + local_index + user_index}"[-4:],
                confirmation_note="Synthetic order only. No real order was placed.",
                pickup_slot_label="5:00 PM - 7:00 PM" if mode == "pickup" else "",
                placed_at=SEED_TIMESTAMP - timedelta(days=local_index * 4 + user_index),
            )
            db.session.add(order)
            db.session.flush()
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=base_product.id,
                    item_name=base_product.name,
                    quantity=1,
                    unit_price=base_product.price,
                    protection_plan_name="",
                )
            )
            if local_index % 3 == 0:
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        product_id=extra_product.id,
                        item_name=extra_product.name,
                        quantity=1,
                        unit_price=extra_product.price,
                        protection_plan_name="",
                    )
                )
            db.session.add(
                PaymentMock(
                    order_id=order.id,
                    amount=total,
                    card_label=order.payment_brand,
                    auth_status="Approved",
                    approval_code=f"APR{order_counter:05d}",
                    created_at=order.placed_at,
                )
            )


def _attach_seed_images(image_root: Path) -> None:
    _write_svg(
        image_root / "hero" / "target-hero.svg",
        "Target local benchmark mirror",
        "Synthetic deals, pickup, delivery, rewards, and checkout tasks",
        ("#8f0000", "#cc0000", "#ffffff"),
        "DEAL",
    )


def _populate_all(image_root: Path) -> None:
    _add_brand_records()
    db.session.flush()
    _add_category_records(image_root)
    db.session.flush()
    _add_store_records(image_root)
    db.session.flush()
    _add_delivery_options()
    db.session.flush()
    products = _persist_products(image_root)
    _add_pickup_slots()
    _add_store_inventory(products)
    _add_reviews(products)
    _add_protection_plans(products)
    _add_support_articles()
    _add_deals(products)
    users = _add_users_and_accounts()
    db.session.flush()
    _add_reward_activity(users)
    _add_support_tickets(users)
    _add_wishlist_compare_cart(users, products)
    _seed_orders(users, products)
    _attach_seed_images(image_root)


def ensure_seed_data(force: bool, runtime_db_path: Path, seed_db_path: Path, image_root: Path) -> None:
    image_root.mkdir(parents=True, exist_ok=True)

    if force or not _counts_ok():
        db.drop_all()
        db.create_all()
        _populate_all(image_root)
        db.session.commit()
        db.session.remove()
        if runtime_db_path.exists():
            seed_db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(runtime_db_path, seed_db_path)
        return

    _ensure_generated_assets(image_root)
    if runtime_db_path.exists() and not seed_db_path.exists():
        seed_db_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime_db_path, seed_db_path)


if __name__ == "__main__":
    from app import app

    with app.app_context():
        ensure_seed_data(
            force=not Path("instance_seed/target.db").exists(),
            runtime_db_path=Path("instance/target.db"),
            seed_db_path=Path("instance_seed/target.db"),
            image_root=Path("static/images"),
        )

