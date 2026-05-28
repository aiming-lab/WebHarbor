import shutil
from datetime import datetime, timedelta
from pathlib import Path


MIRROR_REFERENCE_DATE = datetime(2026, 4, 18, 10, 0, 0)
BENCHMARK_PASSWORD = "TestPass123!"


CATEGORY_DEFS = [
    {"name": "Photography", "slug": "photography", "description": "Camera bodies, lenses, support gear, and storage built for stills workflows.", "hero_copy": "Browse mirrorless cameras, pro lenses, support systems, and storage cards with filter-heavy B&H style browsing.", "icon_label": "Photo", "nav_order": 1},
    {"name": "Video", "slug": "video", "description": "Cinema capture, drones, monitors, and production bundles for hybrid teams.", "hero_copy": "Explore cinema cameras, drones, monitor recorders, and creator-focused video production tools.", "icon_label": "Video", "nav_order": 2},
    {"name": "Audio", "slug": "audio", "description": "Microphones, monitoring, and recording tools for creators and live production.", "hero_copy": "Compare wireless kits, broadcast mics, and reference headphones with pickup and bundle options.", "icon_label": "Audio", "nav_order": 3},
    {"name": "Computers", "slug": "computers", "description": "Workstations, displays, and print gear for post-production and studio delivery.", "hero_copy": "Shop creator laptops, calibration-ready monitors, and output devices with side-by-side spec comparisons.", "icon_label": "Compute", "nav_order": 4},
    {"name": "Lighting", "slug": "lighting", "description": "LED fixtures, modifiers, and kits for photo and video sets.", "hero_copy": "Find compact LEDs, RGB panels, and soft source kits with realistic tech specs and stock badges.", "icon_label": "Light", "nav_order": 5},
    {"name": "Mirrorless Cameras", "slug": "mirrorless-cameras", "parent": "photography", "description": "Hybrid stills and video camera bodies."},
    {"name": "DSLR Cameras", "slug": "dslr-cameras", "parent": "photography", "description": "Optical viewfinder cameras for sports and studio work."},
    {"name": "Camera Lenses", "slug": "camera-lenses", "parent": "photography", "description": "Wide, standard, and telephoto glass across major mounts."},
    {"name": "Tripods & Supports", "slug": "tripods-supports", "parent": "photography", "description": "Travel, studio, and video support tools."},
    {"name": "Memory Cards & Storage", "slug": "memory-cards-storage", "parent": "photography", "description": "Capture media, SSDs, and workflow storage."},
    {"name": "Cinema Cameras", "slug": "cinema-cameras", "parent": "video", "description": "Compact and studio-ready digital cinema tools."},
    {"name": "Drones", "slug": "drones", "parent": "video", "description": "Aerial platforms for creator and production teams."},
    {"name": "Monitors & Recorders", "slug": "monitors-recorders", "parent": "video", "description": "Field monitors, recorders, and director displays."},
    {"name": "Microphones", "slug": "microphones", "parent": "audio", "description": "Wireless, shotgun, and desktop recording microphones."},
    {"name": "Headphones", "slug": "headphones", "parent": "audio", "description": "Reference and field monitoring headphones."},
    {"name": "Laptops", "slug": "laptops", "parent": "computers", "description": "Creator laptops for edit, color, and tethered capture."},
    {"name": "Monitors", "slug": "monitors", "parent": "computers", "description": "Color-critical and office monitors."},
    {"name": "Printers & Scanners", "slug": "printers-scanners", "parent": "computers", "description": "Proofing printers and document/photo scanners."},
    {"name": "Lighting", "slug": "lighting-kits", "parent": "lighting", "description": "LED monolights, RGB panels, and modifiers."},
]


BRAND_DEFS = [
    ("Canon", "Japan", "#d0282b", "Hybrid stills and imaging tools with strong autofocus and creator-friendly ergonomics."),
    ("Nikon", "Japan", "#ffd334", "Photo-forward systems known for dependable handling and deep color."),
    ("Sony", "Japan", "#2a3a63", "Hybrid imaging, creator audio, and monitoring gear with modern connectivity."),
    ("Fujifilm", "Japan", "#7d1f2c", "Compact creator cameras and film-inspired imaging tools."),
    ("Panasonic", "Japan", "#39435f", "Video-centric bodies and compact cinema hardware."),
    ("Blackmagic", "Australia", "#202020", "Cinema capture systems and production monitoring gear."),
    ("Sigma", "Japan", "#54606c", "Art and contemporary lenses with sharp optical design."),
    ("Tamron", "Japan", "#0d6b57", "Flexible travel zooms and compact creator glass."),
    ("DJI", "China", "#1d1d1d", "Aerial and wireless capture tools for modern production."),
    ("Rode", "Australia", "#1776b6", "Portable audio capture and creator microphones."),
    ("Sennheiser", "Germany", "#0a3f8c", "Reference monitoring and broadcast audio solutions."),
    ("SanDisk", "United States", "#cc1f24", "High-speed capture media and rugged SSD storage."),
    ("Lexar", "United States", "#bf7d0a", "Workflow media and creator storage accessories."),
    ("Apple", "United States", "#4d4d4d", "Portable creator computers and calibrated displays."),
    ("Dell", "United States", "#1563c7", "Workstations, creator laptops, and high-resolution monitors."),
    ("BenQ", "Taiwan", "#4f6d52", "Color-accurate displays for editing and retouching."),
    ("Aputure", "China", "#a05b10", "Professional LED lighting systems for location and studio setups."),
    ("Manfrotto", "Italy", "#8f2334", "Tripods and supports for field production."),
    ("Peak Design", "United States", "#333333", "Creator carry gear and modular support accessories."),
    ("Atomos", "Australia", "#ea5a0b", "Field monitors and recorders for production crews."),
    ("Shure", "United States", "#5a1d4c", "Reliable speech, podcast, and broadcast capture."),
    ("ASUS", "Taiwan", "#1e5aa8", "Creator and pro-performance notebooks and monitors."),
    ("Epson", "Japan", "#2e5d98", "Photo output and scanning tools for studio workflows."),
    ("Godox", "China", "#825700", "Accessible lighting tools with strong feature density."),
    ("Benro", "China", "#00584c", "Video heads and compact supports for travel production."),
]


STORE_DEFS = [
    ("NYC SuperStore", "nyc-superstore", "New York", "NY", "420 Demo Ave, Manhattan, NY 10001", "Mon-Sat 9am-8pm", "(212) 555-0140", "Local benchmark pickup counter"),
    ("Brooklyn Creator Desk", "brooklyn-creator-desk", "Brooklyn", "NY", "55 Flatbush Demo Way, Brooklyn, NY 11217", "Daily 10am-7pm", "(718) 555-0111", "Fast bag-and-tag reservation lane"),
    ("Jersey City Pro Hub", "jersey-city-pro-hub", "Jersey City", "NJ", "91 Harbor Plaza, Jersey City, NJ 07302", "Mon-Sat 10am-6pm", "(201) 555-0168", "Broadcast and cinema pickup"),
    ("White Plains Pickup", "white-plains-pickup", "White Plains", "NY", "17 Mamaroneck Ave, White Plains, NY 10601", "Tue-Sun 10am-6pm", "(914) 555-0122", "Suburban pickup desk"),
    ("Los Angeles Creator Hub", "los-angeles-creator-hub", "Los Angeles", "CA", "300 Olive St, Los Angeles, CA 90013", "Daily 10am-7pm", "(323) 555-0185", "West coast same-day counter"),
    ("Chicago Pro Counter", "chicago-pro-counter", "Chicago", "IL", "201 State St, Chicago, IL 60601", "Mon-Sat 9am-7pm", "(312) 555-0199", "Lighting and grip reserve desk"),
    ("Miami Imaging Desk", "miami-imaging-desk", "Miami", "FL", "88 Biscayne Blvd, Miami, FL 33132", "Daily 11am-7pm", "(305) 555-0156", "Aerial and imaging pickup"),
    ("Austin Broadcast Pickup", "austin-broadcast-pickup", "Austin", "TX", "620 Congress Ave, Austin, TX 78701", "Mon-Fri 9am-6pm", "(512) 555-0137", "Compact pro video counter"),
]


USER_DEFS = [
    {"username": "alice_j", "email": "alice.j@test.com", "display_name": "Alice Johnson", "company": "Northlight Weddings", "role": "Photographer"},
    {"username": "bob_c", "email": "bob.c@test.com", "display_name": "Bob Chen", "company": "Studio Meridian", "role": "Video Producer"},
    {"username": "carol_d", "email": "carol.d@test.com", "display_name": "Carol Davis", "company": "Signal Audio", "role": "Podcast Producer"},
    {"username": "david_k", "email": "david.k@test.com", "display_name": "David Kim", "company": "Frame & Color", "role": "Editor"},
]


def slugify(text: str) -> str:
    return (
        text.lower()
        .replace("&", " and ")
        .replace("+", " plus ")
        .replace("/", " ")
        .replace("'", "")
        .replace(",", " ")
        .replace(".", " ")
    ).strip().replace("  ", " ").replace(" ", "-")


def ensure_svg(path: Path, title: str, subtitle: str, accent: str, product_type: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return

    if product_type in {"Mirrorless Camera", "DSLR Camera", "Cinema Camera"}:
        silhouette = """
        <rect x="140" y="120" width="360" height="190" rx="24" fill="#20262b"/>
        <circle cx="315" cy="214" r="82" fill="#11181c" stroke="#bfc7ce" stroke-width="10"/>
        <circle cx="315" cy="214" r="44" fill="none" stroke="{accent}" stroke-width="10"/>
        <rect x="200" y="95" width="82" height="38" rx="8" fill="#2f363d"/>
        <rect x="400" y="106" width="55" height="26" rx="6" fill="#2f363d"/>
        """
    elif product_type == "Lens":
        silhouette = """
        <rect x="180" y="100" width="280" height="240" rx="52" fill="#22292f"/>
        <ellipse cx="320" cy="220" rx="115" ry="120" fill="#12181c" stroke="#c1cad1" stroke-width="12"/>
        <ellipse cx="320" cy="220" rx="60" ry="72" fill="none" stroke="{accent}" stroke-width="12"/>
        <rect x="210" y="130" width="220" height="18" rx="9" fill="#39434c"/>
        <rect x="210" y="295" width="220" height="18" rx="9" fill="#39434c"/>
        """
    elif product_type in {"Tripod", "Support"}:
        silhouette = """
        <rect x="305" y="85" width="34" height="70" rx="10" fill="#22292f"/>
        <line x1="320" y1="150" x2="240" y2="340" stroke="#20262b" stroke-width="18" stroke-linecap="round"/>
        <line x1="320" y1="150" x2="400" y2="340" stroke="#20262b" stroke-width="18" stroke-linecap="round"/>
        <line x1="320" y1="150" x2="320" y2="350" stroke="#20262b" stroke-width="18" stroke-linecap="round"/>
        <circle cx="320" cy="112" r="20" fill="{accent}"/>
        """
    elif product_type in {"Microphone", "Headphones"}:
        silhouette = """
        <rect x="250" y="95" width="140" height="220" rx="52" fill="#22292f"/>
        <rect x="295" y="270" width="50" height="86" rx="16" fill="#22292f"/>
        <line x1="250" y1="140" x2="390" y2="140" stroke="{accent}" stroke-width="10"/>
        <line x1="250" y1="190" x2="390" y2="190" stroke="#b7c0c8" stroke-width="6" stroke-opacity="0.8"/>
        """
    elif product_type in {"Drone"}:
        silhouette = """
        <circle cx="320" cy="220" r="44" fill="#22292f"/>
        <line x1="220" y1="120" x2="290" y2="190" stroke="#22292f" stroke-width="18" stroke-linecap="round"/>
        <line x1="420" y1="120" x2="350" y2="190" stroke="#22292f" stroke-width="18" stroke-linecap="round"/>
        <line x1="220" y1="320" x2="290" y2="250" stroke="#22292f" stroke-width="18" stroke-linecap="round"/>
        <line x1="420" y1="320" x2="350" y2="250" stroke="#22292f" stroke-width="18" stroke-linecap="round"/>
        <circle cx="220" cy="120" r="40" fill="#12181c" stroke="{accent}" stroke-width="10"/>
        <circle cx="420" cy="120" r="40" fill="#12181c" stroke="{accent}" stroke-width="10"/>
        <circle cx="220" cy="320" r="40" fill="#12181c" stroke="{accent}" stroke-width="10"/>
        <circle cx="420" cy="320" r="40" fill="#12181c" stroke="{accent}" stroke-width="10"/>
        """
    elif product_type in {"Laptop", "Monitor", "Monitor/Recorder"}:
        silhouette = """
        <rect x="140" y="95" width="360" height="210" rx="24" fill="#11181c" stroke="#22292f" stroke-width="12"/>
        <rect x="160" y="115" width="320" height="170" rx="12" fill="url(#screen)"/>
        <rect x="260" y="314" width="120" height="18" rx="9" fill="#2a3038"/>
        <rect x="220" y="332" width="200" height="20" rx="10" fill="#22292f"/>
        """
    elif product_type in {"Printer", "Scanner"}:
        silhouette = """
        <rect x="165" y="135" width="310" height="180" rx="26" fill="#22292f"/>
        <rect x="215" y="95" width="210" height="70" rx="14" fill="#353e46"/>
        <rect x="220" y="225" width="200" height="38" rx="8" fill="{accent}"/>
        <rect x="215" y="300" width="210" height="34" rx="8" fill="#11181c"/>
        """
    else:
        silhouette = """
        <rect x="160" y="110" width="320" height="210" rx="34" fill="#22292f"/>
        <circle cx="320" cy="215" r="60" fill="none" stroke="{accent}" stroke-width="12"/>
        <rect x="210" y="145" width="220" height="20" rx="10" fill="#39434c"/>
        """

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420" role="img" aria-label="{title}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#f5f7f7"/>
    <stop offset="100%" stop-color="#dfe7e5"/>
  </linearGradient>
  <linearGradient id="screen" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#203b3b"/>
    <stop offset="100%" stop-color="{accent}"/>
  </linearGradient>
</defs>
<rect width="640" height="420" rx="26" fill="url(#bg)"/>
<rect x="32" y="30" width="150" height="30" rx="15" fill="{accent}" fill-opacity="0.16"/>
<text x="48" y="50" fill="#24423f" font-size="14" font-family="Arial, sans-serif" font-weight="700">B&amp;H DEMO</text>
{silhouette.format(accent=accent)}
<text x="46" y="360" fill="#1e2528" font-size="28" font-family="Arial, sans-serif" font-weight="700">{title[:34]}</text>
<text x="46" y="392" fill="#4f5b60" font-size="18" font-family="Arial, sans-serif">{subtitle[:54]}</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def ensure_misc_assets(base_dir: str) -> None:
    images_dir = Path(base_dir) / "static" / "images"
    ensure_svg(images_dir / "bh-photo-fallback.svg", "B&H Demo", "Deterministic local benchmark asset", "#24423f", "Monitor")


def spec_groups_from_sections(sections):
    return [{"title": title, "rows": rows} for title, rows in sections]


def camera_specs(sensor, megapixels, mount, video, slots, burst, stabilization, battery, weight, autofocus, viewfinder):
    return spec_groups_from_sections(
        [
            ("Key Specs", [("Sensor Size", sensor), ("Effective Megapixels", f"{megapixels} MP"), ("Lens Mount", mount), ("Recording", video)]),
            ("Performance", [("Card Slots", slots), ("Continuous Shooting", burst), ("Stabilization", stabilization), ("Autofocus", autofocus)]),
            ("General", [("Battery Life", battery), ("Viewfinder", viewfinder), ("Weight", weight), ("Warranty", "1 Year Demo Warranty")]),
        ]
    )


def lens_specs(mount, focal, aperture, filter_size, stabilization, close_focus, weight, construction):
    bucket = "Wide" if "16-" in focal or "14-" in focal else "Telephoto" if "70-" in focal or "100-" in focal else "Standard"
    return bucket, spec_groups_from_sections(
        [
            ("Optics", [("Lens Mount", mount), ("Focal Length", focal), ("Maximum Aperture", aperture), ("Optical Design", construction)]),
            ("Focus", [("Image Stabilization", stabilization), ("Minimum Focus Distance", close_focus), ("Filter Thread", filter_size), ("Autofocus Drive", "Linear motor")]),
            ("Physical", [("Weather Resistance", "Dust and moisture sealed"), ("Weight", weight), ("Included Accessories", "Hood, caps, soft case"), ("Warranty", "1 Year Demo Warranty")]),
        ]
    )


def cinema_specs(sensor, video, dynamic_range, media, inputs, weight, mount):
    return spec_groups_from_sections(
        [
            ("Capture", [("Sensor Size", sensor), ("Recording Formats", video), ("Dynamic Range", dynamic_range), ("Lens Mount", mount)]),
            ("Workflow", [("Media Support", media), ("Audio Inputs", inputs), ("Monitoring", "5-inch daylight touchscreen"), ("Power", "NP-F or V-Mount compatible")]),
            ("Physical", [("Body Style", "Production-ready compact cinema body"), ("Weight", weight), ("Warranty", "1 Year Demo Warranty"), ("Notes", "Synthetic local benchmark inventory")]),
        ]
    )


def tripod_specs(material, payload, height, folded, head, weight):
    return spec_groups_from_sections(
        [
            ("Support", [("Material", material), ("Max Payload", payload), ("Max Height", height), ("Folded Length", folded)]),
            ("Head", [("Head Type", head), ("Quick Release", "Arca-compatible"), ("Leg Sections", "4"), ("Feet", "Rubber and spike set")]),
            ("General", [("Weight", weight), ("Warranty", "5 Year Demo Support"), ("Travel Bag", "Included"), ("Use Case", "Synthetic pickup-ready studio support")]),
        ]
    )


def storage_specs(capacity, form_factor, read_speed, write_speed, interface, weight):
    return spec_groups_from_sections(
        [
            ("Media", [("Capacity", capacity), ("Form Factor", form_factor), ("Read Speed", read_speed), ("Write Speed", write_speed)]),
            ("Workflow", [("Interface", interface), ("Capture Use", "Hybrid photo and video"), ("Warranty", "Limited lifetime demo coverage"), ("Ruggedization", "Shock and temperature resistant")]),
            ("Physical", [("Weight", weight), ("Labeling", "Preformatted for deterministic mirror tasks"), ("Color", "Black / graphite"), ("Included", "Protective case or cable where applicable")]),
        ]
    )


def lighting_specs(output, cct, cri, power, control, weight):
    return spec_groups_from_sections(
        [
            ("Light Engine", [("Output", output), ("Color Temperature", cct), ("CRI/TLCI", cri), ("Power Draw", power)]),
            ("Control", [("Control Options", control), ("Effects", "Builtin lighting effects"), ("Cooling", "Low-noise active cooling"), ("Mount", "Bowens or yoke mount")]),
            ("Physical", [("Weight", weight), ("Power Supply", "AC adapter included"), ("Warranty", "1 Year Demo Warranty"), ("Notes", "Local synthetic stock only")]),
        ]
    )


def audio_specs(pattern, response, connectivity, power, weight, bundle_note):
    return spec_groups_from_sections(
        [
            ("Audio", [("Polar Pattern", pattern), ("Frequency Response", response), ("Connectivity", connectivity), ("Power", power)]),
            ("Workflow", [("Monitoring", "3.5mm headphone monitoring"), ("Mounting", bundle_note), ("Compatibility", "Mac, Windows, iOS, and Android demo workflows"), ("Warranty", "2 Year Demo Warranty")]),
            ("Physical", [("Weight", weight), ("Included", "Protective pouch and cables"), ("Finish", "Matte black"), ("Notes", "Synthetic local benchmark media gear")]),
        ]
    )


def drone_specs(sensor, video, flight_time, avoidance, transmission, weight):
    return spec_groups_from_sections(
        [
            ("Flight", [("Sensor", sensor), ("Video", video), ("Max Flight Time", flight_time), ("Obstacle Avoidance", avoidance)]),
            ("Control", [("Transmission", transmission), ("Storage", "Internal plus microSD"), ("Modes", "Follow, orbit, waypoint"), ("Battery", "Two-battery demo kit supported")]),
            ("Physical", [("Weight", weight), ("Warranty", "1 Year Demo Warranty"), ("Notes", "No real flight or registration required"), ("Carrying Case", "Included in Fly More bundles")]),
        ]
    )


def computer_specs(processor, memory, storage, display, ports, connectivity, weight):
    return spec_groups_from_sections(
        [
            ("Performance", [("Processor", processor), ("Memory", memory), ("Storage", storage), ("Display", display)]),
            ("I/O", [("Ports", ports), ("Connectivity", connectivity), ("Color Management", "Factory calibration included"), ("Warranty", "1 Year Demo Warranty")]),
            ("General", [("Weight", weight), ("Use Case", "Editing, ingest, and tethered capture"), ("OS", "Synthetic local benchmark image"), ("Notes", "No external activation required")]),
        ]
    )


def monitor_specs(size, resolution, color, hdr, inputs, weight):
    return spec_groups_from_sections(
        [
            ("Display", [("Panel Size", size), ("Resolution", resolution), ("Color Coverage", color), ("HDR", hdr)]),
            ("Connectivity", [("Inputs", inputs), ("Calibration", "Hardware LUT support"), ("USB Hub", "Integrated"), ("Warranty", "3 Year Demo Panel Coverage")]),
            ("Physical", [("Weight", weight), ("Ergonomics", "Height, tilt, swivel"), ("Included", "Cables and shading hood where applicable"), ("Notes", "Synthetic creator monitor stock")]),
        ]
    )


def printer_specs(media, resolution, speed, ink, connectivity, weight):
    return spec_groups_from_sections(
        [
            ("Output", [("Supported Media", media), ("Max Resolution", resolution), ("Print / Scan Speed", speed), ("Ink or Sensor", ink)]),
            ("Connectivity", [("Connectivity", connectivity), ("Workflow", "Proofing and delivery"), ("Warranty", "1 Year Demo Warranty"), ("Notes", "Synthetic benchmark hardware")]),
            ("Physical", [("Weight", weight), ("Included", "Starter supplies"), ("Footprint", "Studio desktop"), ("Support", "Local-only demo contact flow")]),
        ]
    )


def make_product(
    *,
    name,
    brand,
    category_slug,
    top_category_slug,
    product_type,
    short_description,
    description,
    price,
    list_price,
    rating,
    review_count,
    qa_count,
    best_seller_rank,
    sort_newness,
    accent_color,
    specs,
    search_blob="",
    condition="New",
    availability="In Stock",
    stock_level=14,
    pickup_available=True,
    pickup_message="Ready in 2 hours",
    shipping_message="Free Expedited Shipping",
    return_window="30-Day Return Window",
    warranty="1 Year Demo Warranty",
    product_family="",
    sensor_size="",
    mount_type="",
    focal_length="",
    focal_length_bucket="",
    megapixels=0,
    capacity_gb=0,
    connectivity="",
    release_label="Spring 2025",
    featured=False,
    bundle_anchor=False,
    used_highlight=False,
    variants=None,
    deal_label="",
    deal_type="sale",
):
    slug = slugify(name)
    sku = f"BH{best_seller_rank:05d}"
    return {
        "name": name,
        "slug": slug,
        "sku": sku,
        "brand": brand,
        "category_slug": category_slug,
        "top_category_slug": top_category_slug,
        "subcategory_slug": category_slug,
        "product_type": product_type,
        "product_family": product_family or category_slug,
        "short_description": short_description,
        "description": description,
        "search_blob": search_blob,
        "price": price,
        "list_price": list_price,
        "rating": rating,
        "review_count": review_count,
        "qa_count": qa_count,
        "condition": condition,
        "availability": availability,
        "stock_level": stock_level,
        "pickup_available": pickup_available,
        "pickup_message": pickup_message,
        "shipping_message": shipping_message,
        "return_window": return_window,
        "warranty": warranty,
        "best_seller_rank": best_seller_rank,
        "sort_newness": sort_newness,
        "sensor_size": sensor_size,
        "mount_type": mount_type,
        "focal_length": focal_length,
        "focal_length_bucket": focal_length_bucket,
        "megapixels": megapixels,
        "capacity_gb": capacity_gb,
        "connectivity": connectivity,
        "accent_color": accent_color,
        "release_label": release_label,
        "specs": specs,
        "variants": variants or [],
        "featured": featured,
        "bundle_anchor": bundle_anchor,
        "used_highlight": used_highlight,
        "deal_label": deal_label,
        "deal_type": deal_type,
    }


def mirrorless_products():
    entries = [
        ("Sony Aurora A7X Mirrorless Camera", "Sony", 2498, 2798, 4.8, 188, "Full Frame", "Sony E", 33.0, "4K60 10-bit", "Dual CFexpress A / SD", "10 fps", "5-axis 7-stop IBIS", "610 shots", "673 g", "759k phase-detect", "3.69m-dot OLED EVF", True, True, "Free 2-day shipping"),
        ("Canon Orbit R6 Mark II Mirrorless Camera", "Canon", 2299, 2499, 4.7, 164, "Full Frame", "Canon RF", 24.2, "4K60 oversampled", "Dual SD UHS-II", "12 fps mechanical", "5-axis 8-stop IBIS", "580 shots", "680 g", "Dual Pixel AF II", "3.69m-dot EVF", True, False, "Free expedited shipping"),
        ("Nikon Zenith Z8 Mirrorless Camera", "Nikon", 3496, 3796, 4.9, 146, "Full Frame", "Nikon Z", 45.7, "8.3K60 RAW", "CFexpress B / SD", "20 fps RAW", "5-axis 6-stop VR", "530 shots", "910 g", "3D subject tracking", "3.69m-dot EVF", True, True, "Signature shipping included"),
        ("Fujifilm Northlight X-T5 Mirrorless Camera", "Fujifilm", 1699, 1849, 4.8, 131, "APS-C", "Fujifilm X", 40.2, "6.2K30", "Dual SD UHS-II", "15 fps mechanical", "7-stop IBIS", "680 shots", "557 g", "Deep-learning AF", "3.69m-dot EVF", True, False, "Free 2-day shipping"),
        ("Panasonic Lumix S5 II Mirrorless Camera", "Panasonic", 1997, 2197, 4.7, 119, "Full Frame", "L Mount", 24.2, "6K30 / 4K60", "Dual SD UHS-II", "9 fps mechanical", "5-axis 6.5-stop IBIS", "470 shots", "740 g", "Phase hybrid AF", "3.68m-dot OLED", True, False, "Free shipping"),
        ("Sony Aurora A6700 Mirrorless Camera", "Sony", 1398, 1498, 4.7, 101, "APS-C", "Sony E", 26.0, "4K120", "Single SD UHS-II", "11 fps", "5-axis stabilization", "570 shots", "493 g", "AI subject recognition", "2.36m-dot OLED", True, False, "Fast creator shipping"),
        ("Canon Orbit R8 Mirrorless Camera", "Canon", 1299, 1399, 4.6, 96, "Full Frame", "Canon RF", 24.2, "4K60", "Single SD UHS-II", "6 fps", "Digital stabilization", "420 shots", "461 g", "Dual Pixel AF II", "2.36m-dot EVF", True, False, "Free shipping"),
        ("Nikon Zenith Zf Mirrorless Camera", "Nikon", 1896, 2046, 4.8, 88, "Full Frame", "Nikon Z", 24.5, "4K60", "Dual SD / microSD", "14 fps", "5-axis 8-stop VR", "410 shots", "710 g", "3D tracking", "3.69m-dot EVF", True, False, "Free expedited shipping"),
        ("Fujifilm Northlight X-S20 Mirrorless Camera", "Fujifilm", 1299, 1399, 4.7, 82, "APS-C", "Fujifilm X", 26.1, "6.2K30", "Single SD UHS-II", "8 fps", "7-stop IBIS", "750 shots", "491 g", "Vlog-friendly AF", "2.36m-dot EVF", True, False, "Free shipping"),
        ("Panasonic Lumix GH7 Mirrorless Camera", "Panasonic", 2197, 2397, 4.8, 76, "Micro Four Thirds", "MFT", 25.2, "5.7K60 ProRes", "CFexpress B / SD", "12 fps", "7.5-stop IBIS", "420 shots", "805 g", "Phase hybrid AF", "3.68m-dot OLED", True, False, "Pro video shipping"),
        ("Sony Aurora A1C Mirrorless Camera", "Sony", 4498, 4798, 4.9, 65, "Full Frame", "Sony E", 50.1, "8K30 / 4K120", "Dual CFexpress A / SD", "30 fps", "5-axis 8-stop IBIS", "530 shots", "737 g", "AI subject recognition", "9.44m-dot EVF", True, True, "Priority insured shipping"),
        ("Canon Orbit R50 V Mirrorless Camera", "Canon", 899, 999, 4.5, 73, "APS-C", "Canon RF", 24.2, "4K30", "Single SD UHS-II", "15 fps electronic", "Digital stabilization", "460 shots", "417 g", "Dual Pixel AF II", "2.36m-dot EVF", False, False, "Fast creator shipping"),
    ]
    records = []
    for idx, entry in enumerate(entries, start=1):
        (
            name, brand, price, list_price, rating, review_count, sensor, mount, megapixels, video, slots,
            burst, stabilization, battery, weight, autofocus, viewfinder, featured, bundle_anchor, ship_msg,
        ) = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="mirrorless-cameras",
                top_category_slug="photography",
                product_type="Mirrorless Camera",
                short_description="Hybrid mirrorless camera body for stills, creator video, and controlled studio work.",
                description=f"{name} is part of the local B&H benchmark mirror. It combines responsive autofocus, dependable color, and pro-friendly media options for synthetic creator workflows.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=9 + idx,
                best_seller_rank=idx,
                sort_newness=300 - idx,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=camera_specs(sensor, megapixels, mount, video, slots, burst, stabilization, battery, weight, autofocus, viewfinder),
                search_blob=f"{brand} mirrorless {sensor} {mount} {video} creator camera photo video",
                sensor_size=sensor,
                mount_type=mount,
                megapixels=megapixels,
                connectivity="USB-C, HDMI, Wi-Fi, Bluetooth",
                release_label="Spring 2025" if idx < 6 else "Fall 2024",
                featured=featured,
                bundle_anchor=bundle_anchor,
                variants=[("Body Only", "Kit", "Body Only", 0), ("Creator Kit", "Kit", "Creator Kit", 299)],
                deal_label="Deal Zone" if list_price > price else "",
            )
        )
    return records


def dslr_products(start_rank):
    entries = [
        ("Canon Terra 90D DSLR Camera", "Canon", 1149, 1299, 4.6, 118, 32.5, "Canon EF/EF-S", "4K30", "Single SD UHS-II", "10 fps", "Optical IS via lens", "1300 shots", "701 g"),
        ("Nikon D780 Studio DSLR Camera", "Nikon", 1796, 1946, 4.7, 104, 24.5, "Nikon F", "4K30", "Dual SD UHS-II", "7 fps", "Optical VR via lens", "2260 shots", "840 g"),
        ("Canon Terra Rebel T8 Creator DSLR", "Canon", 749, 829, 4.4, 92, 24.1, "Canon EF/EF-S", "4K24", "Single SD UHS-I", "7 fps", "Lens-based stabilization", "1240 shots", "515 g"),
        ("Nikon D7500 Action DSLR", "Nikon", 896, 996, 4.6, 86, 20.9, "Nikon F", "4K30", "Single SD UHS-I", "8 fps", "Lens-based stabilization", "950 shots", "720 g"),
        ("Canon Terra 5D Classic Refresh DSLR", "Canon", 1499, 1699, 4.5, 66, 30.4, "Canon EF", "4K30", "CF / SD dual", "7 fps", "Lens-based stabilization", "900 shots", "890 g"),
        ("Nikon D850 Heritage DSLR", "Nikon", 2396, 2596, 4.8, 77, 45.7, "Nikon F", "4K30", "XQD / SD dual", "9 fps", "Lens-based stabilization", "1840 shots", "1005 g"),
        ("Canon EOS 6D Mark Lite DSLR", "Canon", 999, 1129, 4.4, 59, 26.2, "Canon EF", "4K24", "Single SD UHS-I", "6.5 fps", "Lens-based stabilization", "1200 shots", "765 g"),
        ("Nikon D5600 Travel DSLR", "Nikon", 699, 799, 4.3, 53, 24.2, "Nikon F", "Full HD", "Single SD UHS-I", "5 fps", "Lens-based stabilization", "970 shots", "465 g"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, mp, mount, video, slots, burst, stabilization, battery, weight = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="dslr-cameras",
                top_category_slug="photography",
                product_type="DSLR Camera",
                short_description="Optical viewfinder camera body for still photography, event coverage, and classroom-friendly capture workflows.",
                description=f"{name} mirrors a DSLR-focused B&H catalog entry with clear media, autofocus, and support notes for offline benchmark browsing.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=6 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=250 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=camera_specs("APS-C" if mp < 25 else "Full Frame", mp, mount, video, slots, burst, stabilization, battery, weight, "Optical phase AF", "Optical pentaprism"),
                search_blob=f"{brand} dslr optical viewfinder {mount} photography camera",
                sensor_size="APS-C" if mp < 25 else "Full Frame",
                mount_type=mount,
                megapixels=mp,
                connectivity="USB, HDMI, Wi-Fi",
                release_label="Heritage Stock",
                variants=[("Body Only", "Kit", "Body Only", 0), ("Starter Lens Kit", "Kit", "Starter Lens Kit", 179)],
                deal_label="Photo Special" if price < list_price else "",
            )
        )
    return records


def lens_products(start_rank):
    entries = [
        ("Sigma ArtLine 24-70mm f/2.8 DG DN Lens", "Sigma", "Sony E", 1099, 1199, 4.8, 142, "24-70mm", "f/2.8", "82mm", "Optical stabilization", "0.18 m", "835 g", "19 elements in 15 groups", "Standard", "New"),
        ("Tamron Travel 70-180mm f/2.8 Di III Lens", "Tamron", "Sony E", 1099, 1179, 4.7, 124, "70-180mm", "f/2.8", "67mm", "VC stabilization", "0.85 m", "810 g", "19 elements in 14 groups", "Telephoto", "New"),
        ("Sony GM 16-35mm f/2.8 II Lens", "Sony", "Sony E", 2098, 2298, 4.9, 97, "16-35mm", "f/2.8", "82mm", "No optical stabilization", "0.22 m", "547 g", "15 elements in 12 groups", "Wide", "New"),
        ("Canon RF 100-500mm f/4.5-7.1L Lens", "Canon", "Canon RF", 2699, 2899, 4.8, 93, "100-500mm", "f/4.5-7.1", "77mm", "Optical stabilization", "0.9 m", "1365 g", "20 elements in 14 groups", "Telephoto", "New"),
        ("Nikon Z 24-120mm f/4 S Lens", "Nikon", "Nikon Z", 1096, 1196, 4.8, 88, "24-120mm", "f/4", "77mm", "No optical stabilization", "0.35 m", "630 g", "16 elements in 13 groups", "Standard", "New"),
        ("Fujifilm XF 33mm f/1.4 R LM Lens", "Fujifilm", "Fujifilm X", 799, 899, 4.7, 82, "33mm", "f/1.4", "58mm", "No optical stabilization", "0.3 m", "360 g", "15 elements in 10 groups", "Standard", "New"),
        ("Sigma ArtLine 85mm f/1.4 DG DN Lens", "Sigma", "Sony E", 999, 1099, 4.8, 75, "85mm", "f/1.4", "77mm", "No optical stabilization", "0.85 m", "625 g", "15 elements in 11 groups", "Telephoto", "Open-Box"),
        ("Tamron Travel 28-75mm f/2.8 G2 Lens", "Tamron", "Sony E", 799, 899, 4.6, 120, "28-75mm", "f/2.8", "67mm", "No optical stabilization", "0.18 m", "540 g", "17 elements in 15 groups", "Standard", "New"),
        ("Sony PZ 16-35mm f/4 G Lens", "Sony", "Sony E", 1198, 1298, 4.7, 71, "16-35mm", "f/4", "72mm", "Power zoom stabilization", "0.24 m", "353 g", "13 elements in 12 groups", "Wide", "New"),
        ("Canon RF 24-105mm f/4L IS Lens", "Canon", "Canon RF", 1299, 1399, 4.7, 116, "24-105mm", "f/4", "77mm", "Optical stabilization", "0.45 m", "700 g", "18 elements in 14 groups", "Standard", "New"),
        ("Nikon Z 70-200mm f/2.8 VR S Lens", "Nikon", "Nikon Z", 2396, 2496, 4.9, 68, "70-200mm", "f/2.8", "77mm", "VR stabilization", "0.5 m", "1360 g", "21 elements in 18 groups", "Telephoto", "New"),
        ("Fujifilm XF 16-55mm f/2.8 WR II Lens", "Fujifilm", "Fujifilm X", 1249, 1349, 4.8, 59, "16-55mm", "f/2.8", "72mm", "No optical stabilization", "0.3 m", "660 g", "15 elements in 11 groups", "Wide", "New"),
        ("Sigma Contemporary 18-50mm f/2.8 DC DN Lens", "Sigma", "Fujifilm X", 549, 629, 4.6, 64, "18-50mm", "f/2.8", "55mm", "No optical stabilization", "0.12 m", "285 g", "13 elements in 10 groups", "Wide", "Used"),
        ("Tamron 17-70mm f/2.8 VC Lens", "Tamron", "Fujifilm X", 749, 849, 4.7, 66, "17-70mm", "f/2.8", "67mm", "VC stabilization", "0.19 m", "525 g", "16 elements in 12 groups", "Standard", "New"),
        ("Sony FE 70-300mm f/4.5-5.6 G Lens", "Sony", "Sony E", 1248, 1348, 4.5, 52, "70-300mm", "f/4.5-5.6", "72mm", "Optical stabilization", "0.9 m", "854 g", "16 elements in 13 groups", "Telephoto", "Open-Box"),
        ("Canon RF 35mm f/1.8 Macro IS Lens", "Canon", "Canon RF", 479, 549, 4.6, 97, "35mm", "f/1.8", "52mm", "Optical stabilization", "0.17 m", "305 g", "11 elements in 9 groups", "Standard", "New"),
        ("Nikon Z 14-30mm f/4 S Lens", "Nikon", "Nikon Z", 1196, 1296, 4.8, 57, "14-30mm", "f/4", "82mm", "No optical stabilization", "0.28 m", "485 g", "14 elements in 12 groups", "Wide", "New"),
        ("Panasonic Lumix 24-105mm f/4 Macro Lens", "Panasonic", "L Mount", 998, 1098, 4.6, 54, "24-105mm", "f/4", "77mm", "Optical stabilization", "0.3 m", "680 g", "16 elements in 13 groups", "Standard", "New"),
        ("Sigma Sports 150-600mm f/5-6.3 DG DN Lens", "Sigma", "Sony E", 1499, 1599, 4.7, 49, "150-600mm", "f/5-6.3", "95mm", "Optical stabilization", "0.58 m", "2100 g", "25 elements in 15 groups", "Telephoto", "Used"),
        ("Canon RF 16mm f/2.8 STM Lens", "Canon", "Canon RF", 279, 329, 4.4, 88, "16mm", "f/2.8", "43mm", "No optical stabilization", "0.13 m", "165 g", "9 elements in 7 groups", "Wide", "New"),
        ("Sony FE 40mm f/2.5 G Lens", "Sony", "Sony E", 548, 598, 4.6, 46, "40mm", "f/2.5", "49mm", "No optical stabilization", "0.28 m", "173 g", "9 elements in 9 groups", "Standard", "Open-Box"),
        ("Nikon Z 50mm f/1.8 S Lens", "Nikon", "Nikon Z", 526, 576, 4.8, 63, "50mm", "f/1.8", "62mm", "No optical stabilization", "0.4 m", "415 g", "12 elements in 9 groups", "Standard", "New"),
        ("Tamron 150-500mm f/5-6.7 Di III VC Lens", "Tamron", "Sony E", 1299, 1399, 4.7, 43, "150-500mm", "f/5-6.7", "82mm", "VC stabilization", "0.6 m", "1725 g", "25 elements in 16 groups", "Telephoto", "New"),
        ("Fujifilm XF 70-300mm f/4-5.6 OIS Lens", "Fujifilm", "Fujifilm X", 749, 829, 4.7, 58, "70-300mm", "f/4-5.6", "67mm", "Optical stabilization", "0.83 m", "580 g", "17 elements in 12 groups", "Telephoto", "New"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        (
            name, brand, mount, price, list_price, rating, review_count, focal, aperture, filter_size,
            stabilization, close_focus, weight, construction, bucket, condition,
        ) = entry
        focal_bucket, specs = lens_specs(mount, focal, aperture, filter_size, stabilization, close_focus, weight, construction)
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="camera-lenses",
                top_category_slug="photography",
                product_type="Lens",
                short_description="Fast interchangeable lens with category-specific optical specs and comparison-friendly rows.",
                description=f"{name} appears in the local B&H Photo mirror with focal length, stabilization, and compatibility details grounded in deterministic demo data.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=7 + (offset % 6),
                best_seller_rank=start_rank + offset,
                sort_newness=220 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=specs,
                search_blob=f"{brand} lens {mount} {focal} {aperture} {bucket.lower()} photography",
                mount_type=mount,
                focal_length=focal,
                focal_length_bucket=focal_bucket,
                connectivity="None",
                condition=condition,
                availability="In Stock" if condition != "Used" else "Limited Stock",
                stock_level=6 if condition != "Used" else 2,
                pickup_message="Ready today" if condition == "New" else "Ready tomorrow",
                shipping_message="Insured lens delivery",
                warranty="1 Year Demo Optics Coverage",
                release_label="Spring 2024",
                variants=[("Standard Finish", "Finish", "Standard Finish", 0), ("Protection Filter Bundle", "Bundle", "Protection Filter Bundle", 39)],
                deal_label="Open-Box" if condition == "Open-Box" else ("Used Deal" if condition == "Used" else "Lens Sale"),
                deal_type="open-box" if condition == "Open-Box" else ("used" if condition == "Used" else "sale"),
                used_highlight=condition != "New",
            )
        )
    return records


def cinema_products(start_rank):
    entries = [
        ("Blackmagic Scout 6K Pro Cinema Camera", "Blackmagic", 2495, 2695, 4.8, 79, "Super 35", "6K Open Gate / 4K120", "13 stops", "CFexpress / USB-C SSD", "Mini XLR dual", "900 g", "Canon EF", True),
        ("Panasonic EVA Core 6K Cinema Camera", "Panasonic", 3299, 3499, 4.7, 51, "Full Frame", "6K60 / 4K120", "14+ stops", "CFexpress B / SD", "Mini XLR dual", "1200 g", "L Mount", True),
        ("Sony FX3 Creator Cinema Camera", "Sony", 3898, 4098, 4.9, 102, "Full Frame", "4K120", "15+ stops", "CFexpress A / SD", "XLR handle included", "715 g", "Sony E", True),
        ("Canon C70 Motion Cinema Camera", "Canon", 4799, 4999, 4.8, 70, "Super 35 DGO", "4K120", "16+ stops", "Dual SD UHS-II", "Mini XLR dual", "1170 g", "Canon RF", True),
        ("Blackmagic Pocket Forge 4K Cinema Camera", "Blackmagic", 1295, 1395, 4.6, 95, "Micro Four Thirds", "4K60", "13 stops", "CFast 2.0 / SD UHS-II", "Mini XLR", "722 g", "MFT", False),
        ("Panasonic BoxCam BGH2 Pro Cinema Camera", "Panasonic", 1697, 1797, 4.5, 48, "Micro Four Thirds", "4K60", "13+ stops", "SD UHS-II", "3.5mm stereo", "545 g", "MFT", False),
        ("Sony FX30 Studio Cinema Camera", "Sony", 1798, 1898, 4.8, 81, "APS-C", "4K120", "14+ stops", "CFexpress A / SD", "XLR via handle", "646 g", "Sony E", True),
        ("Canon R5 C Motion Cinema Camera", "Canon", 3799, 3999, 4.7, 58, "Full Frame", "8K60 RAW", "14+ stops", "CFexpress B / SD", "3.5mm + digital hot shoe", "680 g", "Canon RF", True),
        ("Blackmagic Studio Rack 12K Cinema Camera", "Blackmagic", 5995, 6295, 4.9, 35, "Full Frame", "12K60 RAW", "16 stops", "Dual CFexpress", "Mini XLR quad", "1800 g", "PL Mount", False),
        ("Sony VENI Micro Cinema Unit", "Sony", 6995, 7295, 4.8, 27, "Full Frame", "6K60 / 4K120", "15+ stops", "CFexpress A", "XLR via adapter", "1350 g", "Sony E", False),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, sensor, video, dynamic_range, media, inputs, weight, mount, pickup = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="cinema-cameras",
                top_category_slug="video",
                product_type="Cinema Camera",
                short_description="Compact or production-ready cinema body with media, audio, and DR specs surfaced for comparison tasks.",
                description=f"{name} is mirrored as a deterministic B&H pro video listing with no live services, no firmware checks, and no outside rental or reservation APIs.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=8 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=200 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=cinema_specs(sensor, video, dynamic_range, media, inputs, weight, mount),
                search_blob=f"{brand} cinema camera {sensor} {video} {mount}",
                sensor_size=sensor,
                mount_type=mount,
                connectivity="USB-C, HDMI, Timecode",
                availability="In Stock" if pickup else "Pre-Order",
                stock_level=5 if pickup else 0,
                pickup_available=pickup,
                pickup_message="Pickup at flagship stores" if pickup else "Reserve for first shipment",
                shipping_message="Signature video delivery",
                release_label="Summer 2025",
                bundle_anchor=offset < 4,
                variants=[("Body Only", "Kit", "Body Only", 0), ("Production Bundle", "Kit", "Production Bundle", 499)],
                deal_label="Video Event",
            )
        )
    return records


def support_products(start_rank):
    entries = [
        ("Manfrotto Carbon Travel Tripod Pro", "Manfrotto", 399, 469, 4.7, 94, "Carbon Fiber", "18 lb", "61.8 in", "17.3 in", "Ball Head", "3.2 lb"),
        ("Benro Aero Video Tripod 8X", "Benro", 349, 399, 4.6, 71, "Aluminum", "13.2 lb", "65.1 in", "30.5 in", "Fluid Head", "5.1 lb"),
        ("Peak Design Travel Support Carbon", "Peak Design", 599, 649, 4.8, 85, "Carbon Fiber", "20 lb", "60.2 in", "15.4 in", "Ball Head", "2.8 lb"),
        ("Manfrotto Studio 055 Column Tripod", "Manfrotto", 289, 329, 4.5, 63, "Aluminum", "19.8 lb", "67.2 in", "25.6 in", "Column Head", "5.4 lb"),
        ("Benro Slim Photo Tripod Kit", "Benro", 149, 179, 4.4, 58, "Aluminum", "8.8 lb", "57.5 in", "20.7 in", "Ball Head", "2.9 lb"),
        ("Peak Design Mobile Creator Stand", "Peak Design", 119, 139, 4.3, 49, "Aluminum", "6 lb", "18.3 in", "11.0 in", "Phone Clamp", "1.2 lb"),
        ("Manfrotto Nano Light Stand Duo", "Manfrotto", 99, 119, 4.4, 55, "Aluminum", "3 lb", "73.0 in", "19.0 in", "Stud Mount", "2.1 lb"),
        ("Benro Hydra Adventure Tripod", "Benro", 279, 319, 4.6, 42, "Carbon Fiber", "15.4 lb", "60.1 in", "15.0 in", "Ball Head", "3.4 lb"),
        ("Peak Design Everyday Sling 10L", "Peak Design", 149, 169, 4.7, 88, "Weatherproof Nylon", "10L carry", "n/a", "n/a", "Carry System", "1.9 lb"),
        ("Manfrotto One-Step Monopod Pro", "Manfrotto", 189, 229, 4.5, 39, "Carbon Fiber", "15 lb", "63.0 in", "21.0 in", "Monopod Foot", "2.4 lb"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, material, payload, height, folded, head, weight = entry
        product_type = "Support" if "Sling" in name else "Tripod"
        specs = tripod_specs(material, payload, height, folded, head, weight)
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="tripods-supports",
                top_category_slug="photography",
                product_type=product_type,
                short_description="Support or carry solution with payload, travel, and pickup details surfaced for quick comparison.",
                description=f"{name} is a deterministic support listing used for benchmark tasks around payload, travel size, and pickup availability.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=4 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=180 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=specs,
                search_blob=f"{brand} support tripod bag payload travel creator",
                connectivity="None",
                availability="In Stock" if offset < 8 else "Limited Stock",
                stock_level=9 - (offset % 4),
                pickup_message="Ready in 90 minutes",
                shipping_message="Oversize support shipping" if "Studio" in name else "Free shipping",
                release_label="Creator Support 2025",
                deal_label="Support Sale",
                used_highlight="Sling" in name,
                condition="Used" if "Sling" in name else "New",
            )
        )
    return records


def storage_products(start_rank):
    entries = [
        ("SanDisk Pro Cinema CFexpress Type B 512GB Card", "SanDisk", 279, 319, 4.8, 147, 512, "Card", "1700 MB/s", "1400 MB/s", "CFexpress Type B", "0.03 lb", "New"),
        ("Lexar Gold SDXC 256GB V90 Card", "Lexar", 199, 229, 4.7, 134, 256, "Card", "300 MB/s", "260 MB/s", "SDXC UHS-II", "0.01 lb", "New"),
        ("SanDisk Extreme Portable SSD 2TB", "SanDisk", 189, 219, 4.7, 121, 2048, "Portable SSD", "1050 MB/s", "1000 MB/s", "USB-C 3.2 Gen 2", "0.17 lb", "New"),
        ("Lexar Workflow Dock 4-Bay", "Lexar", 139, 159, 4.5, 76, 0, "Workflow Dock", "n/a", "n/a", "USB-C Dock", "1.5 lb", "New"),
        ("SanDisk Ultra Luxe SDXC 128GB Card", "SanDisk", 39, 49, 4.4, 112, 128, "Card", "150 MB/s", "90 MB/s", "SDXC UHS-I", "0.01 lb", "New"),
        ("Lexar Armor Gold CFexpress 1TB Card", "Lexar", 389, 419, 4.8, 64, 1024, "Card", "1900 MB/s", "1500 MB/s", "CFexpress Type B", "0.03 lb", "New"),
        ("SanDisk ProBlade 4TB SSD Mag", "SanDisk", 349, 399, 4.6, 41, 4096, "SSD Mag", "2000 MB/s", "2000 MB/s", "USB-C Blade", "0.25 lb", "Open-Box"),
        ("Lexar Pro Go Portable SSD 1TB", "Lexar", 119, 139, 4.5, 52, 1024, "Portable SSD", "1050 MB/s", "1000 MB/s", "USB-C 3.2 Gen 2", "0.2 lb", "New"),
        ("SanDisk Creator microSD 512GB Card", "SanDisk", 69, 79, 4.4, 87, 512, "Card", "190 MB/s", "130 MB/s", "microSD UHS-I", "0.01 lb", "New"),
        ("Lexar Silver SDXC 512GB Card", "Lexar", 69, 79, 4.3, 60, 512, "Card", "205 MB/s", "140 MB/s", "SDXC UHS-I", "0.01 lb", "Used"),
        ("SanDisk Rugged Studio SSD 4TB", "SanDisk", 499, 549, 4.7, 34, 4096, "Desktop SSD", "3000 MB/s", "2500 MB/s", "Thunderbolt 4", "1.8 lb", "New"),
        ("Lexar Capture Hub Reader", "Lexar", 79, 89, 4.2, 29, 0, "Card Reader", "n/a", "n/a", "USB-C Reader", "0.25 lb", "New"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, capacity_gb, form_factor, read_speed, write_speed, interface, weight, condition = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="memory-cards-storage",
                top_category_slug="photography",
                product_type="Storage",
                short_description="Capture media or SSD workflow hardware with capacity, speed, and interface filters baked in.",
                description=f"{name} is mirrored as deterministic media inventory with readable throughput specs and creator workflow metadata.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=5 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=160 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=storage_specs(f"{capacity_gb} GB" if capacity_gb and capacity_gb < 1024 else (f"{capacity_gb // 1024} TB" if capacity_gb else "Accessory"), form_factor, read_speed, write_speed, interface, weight),
                search_blob=f"{brand} storage media {form_factor} {capacity_gb}gb {interface}",
                capacity_gb=capacity_gb,
                connectivity=interface,
                availability="In Stock" if condition == "New" else "Limited Stock",
                stock_level=8 if condition == "New" else 2,
                pickup_message="Ready in 1 hour",
                shipping_message="Free media shipping",
                release_label="Workflow 2025",
                condition=condition,
                used_highlight=condition != "New",
                deal_label="Storage Deal" if condition == "New" else condition,
                deal_type="sale" if condition == "New" else condition.lower(),
            )
        )
    return records


def lighting_products(start_rank):
    entries = [
        ("Aputure Storm 300x Bi-Color LED", "Aputure", 949, 1049, 4.8, 96, "58,000 lux at 1m", "2700-6500K", "CRI 96 / TLCI 97", "300W", "Sidus Link app, DMX, onboard", "6.4 lb"),
        ("Godox LiteMax 200 RGB Fixture", "Godox", 499, 569, 4.6, 72, "26,000 lux at 1m", "2800-10,000K RGB", "CRI 95 / TLCI 95", "200W", "Bluetooth app, onboard", "4.8 lb"),
        ("Aputure Nova Slim 1x1 Panel", "Aputure", 699, 779, 4.7, 58, "18,000 lux at 1m", "2700-6500K", "CRI 96 / TLCI 97", "200W", "Sidus Link app, DMX, CRMX", "7.5 lb"),
        ("Godox FlexBeam 100 Portable LED", "Godox", 229, 259, 4.5, 63, "8,500 lux at 1m", "2700-6500K", "CRI 96 / TLCI 96", "100W", "App control, onboard", "2.8 lb"),
        ("Aputure Infinibar 4-Light Kit", "Aputure", 1129, 1249, 4.8, 41, "RGB pixel bar set", "2000-10,000K", "CRI 95 / TLCI 98", "400W total", "App control, DMX, CRMX", "12.0 lb"),
        ("Godox SL150III Daylight Monolight", "Godox", 329, 369, 4.4, 74, "74,300 lux at 1m", "5600K", "CRI 96 / TLCI 97", "160W", "App control, onboard", "4.2 lb"),
        ("Aputure MC Pro Pocket RGB Light", "Aputure", 199, 229, 4.6, 83, "Pocket accent light", "2000-10,000K", "CRI 96 / TLCI 97", "5W", "App control", "0.6 lb"),
        ("Godox TubeFlow RGB Pair", "Godox", 279, 319, 4.5, 34, "RGB tube pair", "2700-8500K", "CRI 95 / TLCI 96", "50W total", "App control", "2.4 lb"),
        ("Aputure Fresnel 2x Modifier", "Aputure", 149, 169, 4.6, 44, "Modifier", "n/a", "n/a", "Passive", "Manual focus beam", "2.1 lb"),
        ("Godox Lantern Dome Softbox 65cm", "Godox", 89, 99, 4.3, 57, "Modifier", "n/a", "n/a", "Passive", "Quick-release mount", "1.8 lb"),
        ("Aputure Amaran 150c RGB Monolight", "Aputure", 359, 399, 4.6, 52, "15,610 lux at 1m", "2500-7500K RGB", "CRI 95 / TLCI 96", "180W", "App control, onboard", "6.0 lb"),
        ("Godox Knowled M300Bi", "Godox", 879, 949, 4.7, 29, "85,700 lux at 1m", "2800-6500K", "CRI 97 / TLCI 98", "330W", "App, DMX, CRMX", "7.4 lb"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, output, cct, cri, power, control, weight = entry
        product_type = "Lighting"
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="lighting-kits",
                top_category_slug="lighting",
                product_type=product_type,
                short_description="Lighting fixture or modifier with output, color, and control specs surfaced for studio shopping tasks.",
                description=f"{name} appears in the local mirror with enough tech detail to compare output, control options, and bundle readiness without contacting any live vendor system.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=4 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=140 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=lighting_specs(output, cct, cri, power, control, weight),
                search_blob=f"{brand} lighting led rgb bi-color output app control",
                connectivity="Bluetooth, DMX" if "DMX" in control else "Bluetooth",
                availability="In Stock",
                stock_level=8,
                pickup_message="Pickup ready by afternoon",
                shipping_message="Studio gear shipping",
                release_label="Studio Light 2025",
                featured=offset < 2,
                deal_label="Lighting Event",
            )
        )
    return records


def microphone_products(start_rank):
    entries = [
        ("Rode Wireless Creator Duo", "Rode", 299, 329, 4.8, 155, "Omnidirectional", "20 Hz - 20 kHz", "2.4 GHz, USB-C, 3.5mm", "Internal battery", "0.3 lb", "Dual transmitter kit"),
        ("DJI Mic Air 2TX Kit", "DJI", 349, 379, 4.7, 101, "Omnidirectional", "50 Hz - 20 kHz", "2.4 GHz, USB-C, Lightning", "Internal battery", "0.35 lb", "Dual transmitter kit"),
        ("Shure MVX2 USB Stream Mic", "Shure", 229, 249, 4.6, 88, "Cardioid", "50 Hz - 16 kHz", "USB-C, 3.5mm", "USB bus power", "0.9 lb", "Desktop yoke mount"),
        ("Rode NTG Creator Shotgun", "Rode", 249, 279, 4.6, 65, "Supercardioid", "20 Hz - 20 kHz", "XLR, 3.5mm", "Phantom / internal battery", "0.55 lb", "Cold-shoe mount"),
        ("Sennheiser MKE Field 600 Shotgun", "Sennheiser", 329, 359, 4.7, 54, "Supercardioid", "40 Hz - 20 kHz", "XLR", "Phantom power", "0.6 lb", "Shock mount included"),
        ("Shure MV7X Voice Broadcast Mic", "Shure", 179, 199, 4.6, 119, "Cardioid", "50 Hz - 16 kHz", "XLR", "Passive", "1.2 lb", "Desktop or boom mount"),
        ("Rode PodMic USB Dynamic Mic", "Rode", 199, 219, 4.7, 82, "Cardioid", "20 Hz - 20 kHz", "USB-C, XLR", "USB bus / XLR", "2.0 lb", "Boom or desk mount"),
        ("DJI Pocket Interview Mic", "DJI", 149, 169, 4.5, 39, "Cardioid", "50 Hz - 18 kHz", "USB-C", "Rechargeable", "0.2 lb", "Handheld interview kit"),
        ("Sennheiser Profile USB Mic", "Sennheiser", 149, 169, 4.5, 61, "Cardioid", "20 Hz - 20 kHz", "USB-C", "USB bus power", "0.77 lb", "Desk stand included"),
        ("Shure MoveMic Reporter Kit", "Shure", 269, 299, 4.4, 28, "Omnidirectional", "50 Hz - 18 kHz", "Bluetooth, USB-C", "Internal battery", "0.42 lb", "Mobile reporter kit"),
        ("Rode Streamer Lavalier Twin", "Rode", 189, 209, 4.4, 31, "Omnidirectional", "20 Hz - 20 kHz", "USB-C adapter", "Plug-in power", "0.18 lb", "Dual clip-on set"),
        ("Sennheiser Accent Podcast Pack", "Sennheiser", 399, 429, 4.6, 26, "Cardioid", "50 Hz - 16 kHz", "USB interface, XLR", "USB + phantom", "2.5 lb", "Interface plus mic bundle"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, pattern, response, connectivity, power, weight, bundle_note = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="microphones",
                top_category_slug="audio",
                product_type="Microphone",
                short_description="Microphone or wireless capture kit with connectivity and monitoring data ready for compare and Q&A tasks.",
                description=f"{name} mirrors an audio-focused B&H listing with demo-only purchasing, local pickup, and no real device activation flow.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=6 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=120 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=audio_specs(pattern, response, connectivity, power, weight, bundle_note),
                search_blob=f"{brand} microphone wireless usb xlr creator audio",
                connectivity=connectivity,
                availability="In Stock",
                stock_level=11 - (offset % 4),
                pickup_message="Ready at audio desks",
                shipping_message="Free audio shipping",
                release_label="Audio 2025",
                featured=offset < 2,
                deal_label="Audio Special",
            )
        )
    return records


def headphone_products(start_rank):
    entries = [
        ("Sennheiser HD 490 Pro Reference Headphones", "Sennheiser", 399, 429, 4.8, 68, "Open-back", "5 Hz - 36 kHz", "Wired 3.5mm / 1/4in", "Passive", "0.72 lb", "Reference mixing"),
        ("Sony Studio MDR-M1 Headphones", "Sony", 249, 279, 4.6, 57, "Closed-back", "5 Hz - 80 kHz", "Wired 3.5mm / 1/4in", "Passive", "0.55 lb", "Recording and monitoring"),
        ("Sennheiser HD 280 Broadcast Headphones", "Sennheiser", 99, 119, 4.5, 122, "Closed-back", "8 Hz - 25 kHz", "Wired 3.5mm / 1/4in", "Passive", "0.63 lb", "Tracking"),
        ("Sony Monitor ZX Pro Headphones", "Sony", 129, 149, 4.4, 74, "Closed-back", "10 Hz - 40 kHz", "Wired 3.5mm", "Passive", "0.47 lb", "Creator desk monitoring"),
        ("Sennheiser Accent BT Creator Headset", "Sennheiser", 229, 249, 4.3, 43, "Closed-back", "18 Hz - 22 kHz", "Bluetooth 5.3, USB-C", "Internal battery", "0.62 lb", "Portable editing"),
        ("Sony OpenMix Spatial Headphones", "Sony", 299, 329, 4.5, 28, "Open-back", "8 Hz - 50 kHz", "Wired and USB-C DAC", "Passive", "0.59 lb", "Spatial reference"),
        ("Sennheiser FieldFold On-Ear Headphones", "Sennheiser", 89, 99, 4.2, 31, "On-ear", "20 Hz - 20 kHz", "Wired 3.5mm", "Passive", "0.36 lb", "Compact field kit"),
        ("Sony Creator ANC Monitor Headphones", "Sony", 349, 379, 4.6, 36, "Closed-back ANC", "10 Hz - 30 kHz", "Bluetooth 5.2, 3.5mm, USB-C", "Internal battery", "0.64 lb", "Travel and edit"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, pattern, response, connectivity, power, weight, bundle_note = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="headphones",
                top_category_slug="audio",
                product_type="Headphones",
                short_description="Monitoring headphones with connection, isolation, and workflow notes suitable for side-by-side comparison tasks.",
                description=f"{name} is a deterministic audio monitoring product in the local B&H mirror with pickup badges and no live warranty lookup.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=3 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=105 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=audio_specs(pattern, response, connectivity, power, weight, bundle_note),
                search_blob=f"{brand} headphones monitor {connectivity} studio",
                connectivity=connectivity,
                availability="In Stock",
                stock_level=10,
                pickup_message="Ready today",
                shipping_message="Free shipping",
                release_label="Monitoring 2025",
                deal_label="Audio Special",
            )
        )
    return records


def drone_products(start_rank):
    entries = [
        ("DJI Airframe 4S Fly More Drone", "DJI", 1399, 1499, 4.8, 92, "1-inch CMOS", "5.4K60", "46 min", "Omnidirectional", "O4 transmission", "1.58 lb"),
        ("DJI Neo Cinema Mini Drone", "DJI", 699, 749, 4.5, 81, "1/1.3-inch CMOS", "4K60 vertical", "31 min", "Forward / downward", "O4 Lite", "0.54 lb"),
        ("DJI Inspire Mini Pro Drone", "DJI", 2199, 2399, 4.7, 49, "4/3 CMOS", "6K30", "38 min", "Omnidirectional", "O4 transmission", "2.4 lb"),
        ("DJI Adventure FPV Combo", "DJI", 999, 1099, 4.4, 36, "1/1.7-inch CMOS", "4K120", "22 min", "Forward sensing", "Low-latency FPV", "1.7 lb"),
        ("DJI Mini Air Travel Drone", "DJI", 499, 549, 4.4, 77, "1/1.3-inch CMOS", "4K30", "34 min", "Tri-directional", "O3 transmission", "0.55 lb"),
        ("DJI Mavic Survey Drone", "DJI", 1899, 1999, 4.6, 28, "4/3 CMOS", "5.1K50", "43 min", "Omnidirectional", "O4 transmission", "2.0 lb"),
        ("DJI Pocket FPV Neo", "DJI", 399, 449, 4.2, 24, "1/2-inch CMOS", "4K30", "18 min", "Downward", "FPV transmission", "0.46 lb"),
        ("DJI Creator Airframe SE", "DJI", 849, 899, 4.5, 31, "1-inch CMOS", "4K60", "39 min", "Forward / backward", "O4 Lite", "0.95 lb"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, sensor, video, flight_time, avoidance, transmission, weight = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="drones",
                top_category_slug="video",
                product_type="Drone",
                short_description="Aerial creator platform with flight time, sensing, and transmission rows designed for filter and comparison tasks.",
                description=f"{name} is part of the local benchmark catalog and never connects to live flight services, geofencing, or registration systems.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=7 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=92 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=drone_specs(sensor, video, flight_time, avoidance, transmission, weight),
                search_blob=f"{brand} drone aerial {video} {sensor} creator",
                connectivity=transmission,
                availability="In Stock" if offset < 6 else "Limited Stock",
                stock_level=4 if offset < 6 else 1,
                pickup_message="Pickup by end of day",
                shipping_message="Adult signature shipping",
                release_label="Aerial 2025",
                featured=offset < 2,
                deal_label="Drone Event",
            )
        )
    return records


def monitor_recorder_products(start_rank):
    entries = [
        ("Atomos Ninja Creator Monitor 5", "Atomos", 699, 759, 4.7, 54, "5-inch 1000 nit touchscreen", "4K60 ProRes", "HDMI in/out, USB-C", "2.5-inch SSD or USB-C media", "0.8 lb"),
        ("Atomos Shogun Studio 7 Monitor Recorder", "Atomos", 1199, 1299, 4.6, 32, "7-inch 2000 nit HDR", "6K30 / 4K120", "HDMI, 12G-SDI, USB-C", "SSD media", "1.9 lb"),
        ("Sony Creator Field Monitor 5", "Sony", 499, 549, 4.5, 41, "5.5-inch daylight display", "4K30 monitoring", "HDMI, USB-C power", "microSD LUT import", "0.9 lb"),
        ("Blackmagic Video Assist 12G 7", "Blackmagic", 995, 1045, 4.7, 36, "7-inch HDR touchscreen", "4K60 BRAW", "12G-SDI, HDMI, USB-C", "Dual SD UHS-II", "1.7 lb"),
        ("Atomos Neon Mobile Director Monitor", "Atomos", 1499, 1599, 4.6, 18, "17-inch on-set display", "4K60 monitoring", "HDMI, 12G-SDI", "External media module", "7.9 lb"),
        ("Blackmagic Pocket View 5 HDR Monitor", "Blackmagic", 429, 469, 4.4, 22, "5-inch HDR touch display", "4K monitoring", "HDMI, USB-C power", "LUTs via SD card", "0.7 lb"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, panel, recording, connectivity, media, weight = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="monitors-recorders",
                top_category_slug="video",
                product_type="Monitor/Recorder",
                short_description="Field monitor or recorder with brightness, recording, and I/O data tailored for compare-heavy production tasks.",
                description=f"{name} is mirrored as a local-only monitoring listing with no firmware downloads, live media activation, or external service calls.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=5 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=88 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=monitor_specs(panel, recording, "LUT and waveform tools", "HDR-ready", connectivity, weight),
                search_blob=f"{brand} monitor recorder field display {recording} {connectivity}",
                connectivity=connectivity,
                availability="In Stock",
                stock_level=5,
                pickup_message="Ready at pro video counters",
                shipping_message="Protected display shipping",
                release_label="Production Monitor 2025",
                featured=offset < 2,
                deal_label="Video Special",
            )
        )
    return records


def laptop_products(start_rank):
    entries = [
        ("Apple CreatorBook 14 M3 Pro Laptop", "Apple", 2399, 2499, 4.8, 87, "M3 Pro 12-core", "36GB unified memory", "1TB SSD", "14.2-inch 3024x1964 mini-LED", "Thunderbolt 4 x3, HDMI, SDXC", "Wi-Fi 6E, Bluetooth 5.3", "3.5 lb"),
        ("Dell Precision Edge 16 Laptop", "Dell", 2699, 2849, 4.7, 63, "Intel Core Ultra 9", "32GB DDR5", "2TB SSD", "16-inch 3840x2400 OLED", "Thunderbolt 4 x2, HDMI, SD", "Wi-Fi 7, Bluetooth 5.4", "4.4 lb"),
        ("ASUS ProArt Studio 13 OLED Laptop", "ASUS", 1899, 1999, 4.6, 58, "AMD Ryzen AI 9", "32GB LPDDR5X", "1TB SSD", "13.3-inch 2880x1800 OLED", "USB4, HDMI, USB-A, SD", "Wi-Fi 6E, Bluetooth 5.3", "3.3 lb"),
        ("Apple CreatorBook 16 Max Laptop", "Apple", 3199, 3349, 4.9, 51, "M3 Max 16-core", "48GB unified memory", "1TB SSD", "16.2-inch 3456x2234 mini-LED", "Thunderbolt 4 x3, HDMI, SDXC", "Wi-Fi 6E, Bluetooth 5.3", "4.7 lb"),
        ("Dell Mobile Color 14 Laptop", "Dell", 1599, 1699, 4.5, 44, "Intel Core Ultra 7", "16GB DDR5", "1TB SSD", "14-inch 2880x1800 OLED", "Thunderbolt 4 x2, HDMI", "Wi-Fi 6E, Bluetooth 5.3", "3.2 lb"),
        ("ASUS ProArt Studio 16 Laptop", "ASUS", 2299, 2399, 4.7, 39, "AMD Ryzen 9", "32GB DDR5", "2TB SSD", "16-inch 3840x2400 OLED", "USB4, HDMI, USB-A, SD Express", "Wi-Fi 6E, Bluetooth 5.3", "4.5 lb"),
        ("Apple CreatorBook Air 15 Laptop", "Apple", 1499, 1599, 4.6, 72, "M3 8-core", "24GB unified memory", "512GB SSD", "15.3-inch 2880x1864 Liquid Retina", "MagSafe, USB-C x2", "Wi-Fi 6E, Bluetooth 5.3", "3.3 lb"),
        ("Dell Creator Compact 13 Laptop", "Dell", 1399, 1499, 4.4, 33, "Intel Core Ultra 5", "16GB LPDDR5", "512GB SSD", "13.4-inch 1920x1200 IPS", "USB-C x2, USB-A", "Wi-Fi 6E, Bluetooth 5.3", "2.9 lb"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, processor, memory, storage, display, ports, connectivity, weight = entry
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="laptops",
                top_category_slug="computers",
                product_type="Laptop",
                short_description="Creator laptop with performance, display, and port detail rows designed for real shopping-style filtering and compare tasks.",
                description=f"{name} is a deterministic creator notebook listing with no live financing, warranty registration, or software activation.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=5 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=80 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=computer_specs(processor, memory, storage, display, ports, connectivity, weight),
                search_blob=f"{brand} laptop creator {processor} {memory} {storage} {display}",
                capacity_gb=2048 if "2TB" in storage else (1024 if "1TB" in storage else 512),
                connectivity=connectivity,
                availability="In Stock",
                stock_level=6,
                pickup_message="Ready in 2 hours",
                shipping_message="Free insured shipping",
                release_label="Compute 2025",
                featured=offset < 2,
                deal_label="Creator Laptop Sale",
            )
        )
    return records


def monitor_products(start_rank):
    entries = [
        ("BenQ ColorPro 32 PD3225U Monitor", "BenQ", 1199, 1299, 4.8, 58, "31.5-inch", "3840x2160", "95% P3 / 99% Rec.709", "DisplayHDR 400", "Thunderbolt 4, HDMI, DP, USB-C", "18.5 lb"),
        ("Dell UltraSharp 32 Thunderbolt Monitor", "Dell", 1399, 1499, 4.6, 43, "32-inch", "3840x2160", "98% DCI-P3", "DisplayHDR 600", "Thunderbolt 4, HDMI, DP, USB hub", "20.0 lb"),
        ("Apple Studio Panel 27 Monitor", "Apple", 1599, 1599, 4.7, 64, "27-inch", "5120x2880", "P3 wide color", "600 nits", "Thunderbolt 3, USB-C x3", "13.9 lb"),
        ("ASUS ProArt 27 PA279CRV Monitor", "ASUS", 499, 549, 4.5, 72, "27-inch", "3840x2160", "99% DCI-P3 / Adobe RGB", "HDR10", "USB-C, HDMI, DP, USB hub", "15.2 lb"),
        ("BenQ SW272U Photo Monitor", "BenQ", 799, 879, 4.7, 37, "27-inch", "3840x2160", "99% Adobe RGB", "HDR10", "USB-C, HDMI, DP", "17.1 lb"),
        ("Dell DualView 40 Creator Monitor", "Dell", 1699, 1799, 4.6, 28, "40-inch", "5120x2160", "98% DCI-P3", "DisplayHDR 600", "Thunderbolt 4, HDMI, DP, Ethernet", "31.0 lb"),
        ("Apple Studio Panel Nano 27 Monitor", "Apple", 1899, 1899, 4.8, 25, "27-inch", "5120x2880", "P3 wide color", "600 nits", "Thunderbolt 3, USB-C x3", "14.1 lb"),
        ("ASUS CreatorView 32 OLED Monitor", "ASUS", 1299, 1399, 4.6, 23, "31.5-inch", "3840x2160 OLED", "99% DCI-P3", "HDR10", "USB-C, HDMI, DP", "18.8 lb"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, size, resolution, color, hdr, inputs, weight = entry
        condition = "Open-Box" if "SW272U" in name else "New"
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="monitors",
                top_category_slug="computers",
                product_type="Monitor",
                short_description="Creator display with clear panel, color, and input data for side-by-side compare workflows.",
                description=f"{name} is mirrored with a spec-heavy retailer-style presentation for color, connectivity, and pickup benchmarking.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=4 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=72 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=monitor_specs(size, resolution, color, hdr, inputs, weight),
                search_blob=f"{brand} monitor color {resolution} {size} {inputs}",
                connectivity=inputs,
                availability="In Stock" if condition == "New" else "Limited Stock",
                stock_level=5 if condition == "New" else 1,
                pickup_message="Pickup available in select stores",
                shipping_message="Oversize monitor shipping",
                release_label="Display 2025",
                condition=condition,
                used_highlight=condition != "New",
                deal_label="Open-Box" if condition != "New" else "Monitor Sale",
                deal_type="open-box" if condition != "New" else "sale",
            )
        )
    return records


def printer_products(start_rank):
    entries = [
        ("Epson P900 Fine Art Photo Printer", "Epson", 1195, 1295, 4.7, 52, "13-inch sheets and roll media", "5760 x 1440 dpi", "1.5 min A3+", "UltraChrome PRO10", "USB, Ethernet, Wi-Fi", "35.7 lb"),
        ("Canon ImagePRO ScanLite 400", "Canon", 699, 779, 4.4, 29, "A4 document and photo scanning", "4800 dpi", "4 sec per photo", "CIS scanner", "USB 3.0", "9.8 lb"),
        ("Epson V850 Archival Photo Scanner", "Epson", 999, 1099, 4.7, 41, "Film and reflective originals", "6400 dpi", "1 min per 35mm strip", "Dual-lens CCD", "USB 2.0", "14.0 lb"),
        ("Canon PIXStudio Pro 200 Printer", "Canon", 599, 649, 4.5, 38, "13-inch sheets", "4800 x 2400 dpi", "90 sec A3+", "Dye ink 8-color", "USB, Wi-Fi, Ethernet", "32.0 lb"),
        ("Epson SureColor P700 Compact Printer", "Epson", 799, 869, 4.6, 34, "13-inch sheets and roll media", "5760 x 1440 dpi", "2 min A3+", "UltraChrome PRO10", "USB, Wi-Fi, Ethernet", "28.0 lb"),
        ("Canon ScanGear Film 900", "Canon", 349, 399, 4.3, 19, "Film and photo scanning", "4800 dpi", "35 sec 35mm frame", "CIS scanner", "USB-C", "7.1 lb"),
        ("Epson EcoProof Label Printer", "Epson", 249, 279, 4.2, 24, "Shipping and asset labels", "600 dpi", "4 ips", "Pigment ink", "USB, Ethernet", "11.3 lb"),
        ("Canon DocumentFlow D120 Scanner", "Canon", 429, 479, 4.4, 21, "A4 office scanning", "600 dpi", "45 ppm", "CIS scanner", "USB 3.0", "8.2 lb"),
    ]
    records = []
    for offset, entry in enumerate(entries):
        name, brand, price, list_price, rating, review_count, media, resolution, speed, ink, connectivity, weight = entry
        product_type = "Scanner" if "Scanner" in name or "Scan" in name else "Printer"
        records.append(
            make_product(
                name=name,
                brand=brand,
                category_slug="printers-scanners",
                top_category_slug="computers",
                product_type=product_type,
                short_description="Output or scanning hardware with media, resolution, and workflow spec rows for benchmark product tasks.",
                description=f"{name} mirrors a pro output listing with deterministic shipping, stock, and support flows inside the local benchmark environment.",
                price=price,
                list_price=list_price,
                rating=rating,
                review_count=review_count,
                qa_count=3 + offset,
                best_seller_rank=start_rank + offset,
                sort_newness=64 - offset,
                accent_color=next(color for b, _origin, color, _blurb in BRAND_DEFS if b == brand),
                specs=printer_specs(media, resolution, speed, ink, connectivity, weight),
                search_blob=f"{brand} printer scanner photo output {media}",
                connectivity=connectivity,
                availability="In Stock",
                stock_level=3 + (offset % 3),
                pickup_message="Pickup at print workflow counters",
                shipping_message="Freight-safe shipping",
                release_label="Output 2025",
                deal_label="Print Studio Sale",
            )
        )
    return records


def build_products():
    products = []
    products.extend(mirrorless_products())
    products.extend(dslr_products(len(products) + 1))
    products.extend(lens_products(len(products) + 1))
    products.extend(cinema_products(len(products) + 1))
    products.extend(support_products(len(products) + 1))
    products.extend(storage_products(len(products) + 1))
    products.extend(lighting_products(len(products) + 1))
    products.extend(microphone_products(len(products) + 1))
    products.extend(headphone_products(len(products) + 1))
    products.extend(drone_products(len(products) + 1))
    products.extend(monitor_recorder_products(len(products) + 1))
    products.extend(laptop_products(len(products) + 1))
    products.extend(monitor_products(len(products) + 1))
    products.extend(printer_products(len(products) + 1))
    return products


def create_reviews(product, ProductReview):
    templates = [
        ("Reliable for paid work", "Used this on three recent shoots and the deterministic B&H mirror details lined up perfectly with the specs and pickup messaging."),
        ("Great balance of value and features", "The spec presentation makes it easy to compare against similar options without the page hiding the important workflow details."),
        ("Solid creator workflow fit", "Shipping notes, accessories, and compatibility sections felt like a real retailer experience while staying fully local and synthetic."),
    ]
    reviews = []
    desired = 2 if product.best_seller_rank <= 40 else 1
    for index in range(desired):
        headline, body = templates[(product.id + index) % len(templates)]
        reviews.append(
            ProductReview(
                product_id=product.id,
                author_name=["Alex M.", "Jordan P.", "Samira L.", "Miles C."][(product.id + index) % 4],
                headline=headline,
                body=f"{body} {product.name} handled as expected in this demo environment.",
                rating=5 if index == 0 or product.rating >= 4.7 else 4,
                verified_purchase=True,
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=(product.id + index) % 120),
            )
        )
    return reviews


def create_questions(product, ProductQuestion, ProductAnswer):
    prompts = [
        ("Does this include a charger or power supply in the box?", "Yes. The demo listing includes the default power accessories noted in the spec and package section."),
        ("Is local store pickup supported for this item?", "Pickup is available anywhere the store inventory block shows stock. This mirror uses deterministic synthetic availability."),
        ("Will this work for a hybrid photo and video workflow?", "It is positioned for hybrid creator use in the local mirror and the technical specs reflect that workflow emphasis."),
        ("Does this ship with cables or core accessories?", "Yes. Included accessories are listed in the spec groups and remain stable for benchmark tasks."),
    ]
    qa_pairs = []
    count = 2 if product.best_seller_rank <= 60 else 1
    for index in range(count):
        question_text, answer_text = prompts[(product.id + index) % len(prompts)]
        question = ProductQuestion(
            product_id=product.id,
            question=question_text,
            asker_name=["Priya", "Ethan", "Nina", "Oscar"][(product.id + index) % 4],
            created_at=MIRROR_REFERENCE_DATE - timedelta(days=(product.id + index) % 90),
        )
        qa_pairs.append((question, answer_text))
    return qa_pairs


def bundle_definitions():
    return [
        ("Sony Hybrid Creator Kit", ["sony-aurora-a7x-mirrorless-camera", "sigma-artline-24-70mm-f-2-8-dg-dn-lens", "sandisk-pro-cinema-cfexpress-type-b-512gb-card"], 3499, 3796, "Featured", "Photo/video hybrid creators"),
        ("Canon Wedding Coverage Bundle", ["canon-orbit-r6-mark-ii-mirrorless-camera", "canon-rf-24-105mm-f-4l-is-lens", "peak-design-everyday-sling-10l"], 3449, 3667, "Bundle", "Event photographers"),
        ("Nikon Long Zoom Field Kit", ["nikon-zenith-z8-mirrorless-camera", "nikon-z-70-200mm-f-2-8-vr-s-lens", "manfrotto-carbon-travel-tripod-pro"], 6099, 6291, "Bundle", "Sports and wildlife"),
        ("Fujifilm Street Story Pack", ["fujifilm-northlight-x-t5-mirrorless-camera", "fujifilm-xf-33mm-f-1-4-r-lm-lens", "peak-design-everyday-sling-10l"], 2499, 2647, "Bundle", "Travel creators"),
        ("Panasonic Video Starter Rig", ["panasonic-lumix-s5-ii-mirrorless-camera", "panasonic-lumix-24-105mm-f-4-macro-lens", "atomos-ninja-creator-monitor-5"], 3299, 3465, "Bundle", "Hybrid capture"),
        ("Blackmagic Documentary Rig", ["blackmagic-scout-6k-pro-cinema-camera", "sigma-sports-150-600mm-f-5-6-3-dg-dn-lens", "sandisk-rugged-studio-ssd-4tb"], 4099, 4293, "Featured", "Documentary teams"),
        ("Audio Creator Desk Pack", ["shure-mvx2-usb-stream-mic", "sennheiser-hd-490-pro-reference-headphones", "dell-mobile-color-14-laptop"], 2049, 2177, "Bundle", "Podcast desks"),
        ("DJI Travel Interview Kit", ["dji-mic-air-2tx-kit", "dji-neo-cinema-mini-drone", "sandisk-extreme-portable-ssd-2tb"], 1199, 1297, "Bundle", "Travel storytellers"),
        ("Aputure Lighting Interview Pack", ["aputure-storm-300x-bi-color-led", "aputure-fresnel-2x-modifier", "manfrotto-nano-light-stand-duo"], 1169, 1247, "Bundle", "Single-subject lighting"),
        ("Color Grade Suite", ["benq-colorpro-32-pd3225u-monitor", "apple-creatorbook-14-m3-pro-laptop", "sandisk-rugged-studio-ssd-4tb"], 3949, 4097, "Featured", "Editors and colorists"),
        ("Field Audio Capture Pack", ["rode-wireless-creator-duo", "sennheiser-profile-usb-mic", "sony-creator-anc-monitor-headphones"], 699, 817, "Bundle", "Mobile interviews"),
        ("Photo Archiving Workflow", ["epson-v850-archival-photo-scanner", "epson-p900-fine-art-photo-printer", "lexar-workflow-dock-4-bay"], 2199, 2333, "Bundle", "Archive and print"),
        ("Compact Production Monitor Kit", ["atomos-ninja-creator-monitor-5", "sony-fx30-studio-cinema-camera", "sandisk-pro-cinema-cfexpress-type-b-512gb-card"], 2399, 2526, "Bundle", "Video crews"),
        ("Drone Survey Pack", ["dji-mavic-survey-drone", "sandisk-creator-microsd-512gb-card", "apple-creatorbook-air-15-laptop"], 3299, 3497, "Bundle", "Aerial mapping"),
        ("Travel Vlog Essentials", ["canon-orbit-r50-v-mirrorless-camera", "dji-pocket-interview-mic", "benro-slim-photo-tripod-kit"], 1189, 1247, "Bundle", "One-person crews"),
        ("Studio Monitor Match Set", ["dell-ultrasharp-32-thunderbolt-monitor", "asus-proart-27-pa279crv-monitor", "apple-studio-panel-27-monitor"], 3299, 3497, "Bundle", "Multi-monitor suites"),
        ("Creator Laptop Pair", ["apple-creatorbook-14-m3-pro-laptop", "asus-proart-studio-13-oled-laptop"], 4049, 4298, "Bundle", "Capture and edit duo"),
        ("Wedding Dual Body Set", ["canon-orbit-r6-mark-ii-mirrorless-camera", "nikon-zenith-zf-mirrorless-camera", "lexar-gold-sdxc-256gb-v90-card"], 4499, 4694, "Bundle", "Two body coverage"),
        ("Podcast Launch Bundle", ["shure-mv7x-voice-broadcast-mic", "sennheiser-accent-podcast-pack", "dell-creator-compact-13-laptop"], 1899, 1987, "Bundle", "New podcast launches"),
        ("RGB Practical Lighting Set", ["godox-tubeflow-rgb-pair", "aputure-mc-pro-pocket-rgb-light", "peak-design-mobile-creator-stand"], 499, 557, "Bundle", "On-location accents"),
    ]


def ensure_visual_assets(base_dir: str, products, bundles):
    ensure_misc_assets(base_dir)
    images_root = Path(base_dir) / "static" / "images"
    products_root = images_root / "products"
    bundles_root = images_root / "bundles"
    for product in products:
        image_path = products_root / f"{product['slug']}.svg"
        ensure_svg(image_path, product["brand"], product["name"], product["accent_color"], product["product_type"])
        product["image_path"] = f"images/products/{product['slug']}.svg"
    for bundle in bundles:
        ensure_svg(
            bundles_root / f"{bundle['slug']}.svg",
            bundle["title"],
            bundle["audience"],
            "#24423f",
            "Monitor",
        )
        bundle["image_path"] = f"images/bundles/{bundle['slug']}.svg"


def seed_database(db, models, base_dir: str):
    Product = models["Product"]
    if Product.query.count() > 0:
        return

    Category = models["Category"]
    Brand = models["Brand"]
    ProductImage = models["ProductImage"]
    ProductSpecGroup = models["ProductSpecGroup"]
    ProductSpec = models["ProductSpec"]
    ProductVariant = models["ProductVariant"]
    ProductReview = models["ProductReview"]
    ProductQuestion = models["ProductQuestion"]
    ProductAnswer = models["ProductAnswer"]
    Bundle = models["Bundle"]
    BundleItem = models["BundleItem"]
    StoreLocation = models["StoreLocation"]
    StoreInventory = models["StoreInventory"]
    Deal = models["Deal"]

    category_by_slug = {}
    for item in CATEGORY_DEFS:
        category = Category(
            name=item["name"],
            slug=item["slug"],
            description=item.get("description", ""),
            hero_copy=item.get("hero_copy", item.get("description", "")),
            icon_label=item.get("icon_label", item["name"][:4]),
            nav_order=item.get("nav_order", 99),
        )
        db.session.add(category)
        category_by_slug[item["slug"]] = category
    db.session.flush()
    for item in CATEGORY_DEFS:
        if item.get("parent"):
            category_by_slug[item["slug"]].parent_id = category_by_slug[item["parent"]].id

    brand_by_name = {}
    for name, origin, color, blurb in BRAND_DEFS:
        brand = Brand(name=name, slug=slugify(name), origin=origin, badge_color=color, blurb=blurb)
        db.session.add(brand)
        brand_by_name[name] = brand
    db.session.flush()

    product_blueprints = build_products()
    bundle_blueprints = [
        {"title": title, "slug": slugify(title), "items": items, "bundle_price": bundle_price, "list_price": list_price, "badge": badge, "audience": audience}
        for title, items, bundle_price, list_price, badge, audience in bundle_definitions()
    ]
    ensure_visual_assets(base_dir, product_blueprints, bundle_blueprints)

    products_by_slug = {}
    created_products = []
    for blueprint in product_blueprints:
        product = Product(
            category_id=category_by_slug[blueprint["category_slug"]].id,
            brand_id=brand_by_name[blueprint["brand"]].id,
            name=blueprint["name"],
            slug=blueprint["slug"],
            sku=blueprint["sku"],
            short_description=blueprint["short_description"],
            description=blueprint["description"],
            search_blob=blueprint["search_blob"],
            price=blueprint["price"],
            list_price=blueprint["list_price"],
            rating=blueprint["rating"],
            review_count=blueprint["review_count"],
            qa_count=blueprint["qa_count"],
            condition=blueprint["condition"],
            availability=blueprint["availability"],
            stock_level=blueprint["stock_level"],
            pickup_available=blueprint["pickup_available"],
            pickup_message=blueprint["pickup_message"],
            shipping_message=blueprint["shipping_message"],
            return_window=blueprint["return_window"],
            warranty=blueprint["warranty"],
            best_seller_rank=blueprint["best_seller_rank"],
            sort_newness=blueprint["sort_newness"],
            top_category_slug=blueprint["top_category_slug"],
            subcategory_slug=blueprint["subcategory_slug"],
            product_family=blueprint["product_family"],
            product_type=blueprint["product_type"],
            sensor_size=blueprint["sensor_size"],
            mount_type=blueprint["mount_type"],
            focal_length=blueprint["focal_length"],
            focal_length_bucket=blueprint["focal_length_bucket"],
            megapixels=blueprint["megapixels"],
            capacity_gb=blueprint["capacity_gb"],
            connectivity=blueprint["connectivity"],
            image_path=blueprint["image_path"],
            accent_color=blueprint["accent_color"],
            release_label=blueprint["release_label"],
            is_featured=blueprint["featured"],
            is_bundle_anchor=blueprint["bundle_anchor"],
            is_used_highlight=blueprint["used_highlight"],
        )
        db.session.add(product)
        db.session.flush()
        products_by_slug[product.slug] = product
        created_products.append((product, blueprint))

        for order, label in enumerate(["Primary", "Detail", "Kit View"]):
            db.session.add(ProductImage(product_id=product.id, path=product.image_path, label=label, sort_order=order))

        for group_order, group in enumerate(blueprint["specs"]):
            spec_group = ProductSpecGroup(product_id=product.id, title=group["title"], sort_order=group_order)
            db.session.add(spec_group)
            db.session.flush()
            for spec_order, (spec_name, spec_value) in enumerate(group["rows"]):
                db.session.add(
                    ProductSpec(
                        group_id=spec_group.id,
                        name=spec_name,
                        value=spec_value,
                        sort_order=spec_order,
                    )
                )

        for order, variant in enumerate(blueprint["variants"]):
            label, variant_type, value, delta = variant
            db.session.add(
                ProductVariant(
                    product_id=product.id,
                    label=label,
                    variant_type=variant_type,
                    value=value,
                    price_delta=delta,
                )
            )

        if blueprint["deal_label"]:
            db.session.add(
                Deal(
                    product_id=product.id,
                    label=blueprint["deal_label"],
                    sale_price=blueprint["price"],
                    deal_type=blueprint["deal_type"],
                    is_active=True,
                )
            )

    stores = []
    for name, slug, city, state, address, hours, phone, note in STORE_DEFS:
        store = StoreLocation(
            name=name,
            slug=slug,
            city=city,
            state=state,
            address=address,
            pickup_hours=hours,
            contact_phone=phone,
            inventory_note=note,
        )
        db.session.add(store)
        stores.append(store)
    db.session.flush()

    for product, blueprint in created_products:
        store_count = 0
        for store_index, store in enumerate(stores):
            seed = sum(ord(char) for char in f"{product.slug}{store.slug}")
            quantity = 0
            if product.pickup_available and product.availability != "Pre-Order":
                quantity = seed % 6
                if product.condition != "New":
                    quantity = min(quantity, 2)
            pickup_eta = "Ready in 2 hours" if quantity >= 3 else "Ready tomorrow after 11:00"
            db.session.add(
                StoreInventory(
                    store_id=store.id,
                    product_id=product.id,
                    quantity=quantity,
                    pickup_eta=pickup_eta,
                )
            )
            if quantity > 0:
                store_count += 1
        product.pickup_store_count = store_count

    review_rows = []
    question_rows = []
    answer_rows = []
    for product, _blueprint in created_products:
        review_rows.extend(create_reviews(product, ProductReview))
        for question, answer_text in create_questions(product, ProductQuestion, ProductAnswer):
            db.session.add(question)
            db.session.flush()
            answer_rows.append(
                ProductAnswer(
                    question_id=question.id,
                    responder_name=["B&H Demo Team", "Store Specialist", "Workflow Advisor"][question.id % 3],
                    answer=answer_text,
                    created_at=question.created_at + timedelta(hours=12),
                )
            )
    db.session.add_all(review_rows)
    db.session.add_all(answer_rows)

    for bundle_blueprint in bundle_blueprints:
        bundle = Bundle(
            title=bundle_blueprint["title"],
            slug=bundle_blueprint["slug"],
            description=f"{bundle_blueprint['title']} collects compatible items into a deterministic checkout-ready package for benchmark tasks.",
            image_path=bundle_blueprint["image_path"],
            bundle_price=bundle_blueprint["bundle_price"],
            list_price=bundle_blueprint["list_price"],
            badge=bundle_blueprint["badge"],
            audience=bundle_blueprint["audience"],
            featured=bundle_blueprint["badge"] == "Featured",
        )
        db.session.add(bundle)
        db.session.flush()
        for item_slug in bundle_blueprint["items"]:
            db.session.add(BundleItem(bundle_id=bundle.id, product_id=products_by_slug[item_slug].id, quantity=1))

    db.session.commit()


def seed_benchmark_users(db, models):
    User = models["User"]
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    Address = models["Address"]
    CartItem = models["CartItem"]
    WishlistItem = models["WishlistItem"]
    CompareItem = models["CompareItem"]
    Order = models["Order"]
    OrderItem = models["OrderItem"]
    StoreReservation = models["StoreReservation"]
    StoreLocation = models["StoreLocation"]
    Product = models["Product"]

    stores = StoreLocation.query.order_by(StoreLocation.id).all()
    products = {product.slug: product for product in Product.query.all()}
    created_users = []

    for index, user_data in enumerate(USER_DEFS):
        user = User(
            email=user_data["email"],
            username=user_data["username"],
            display_name=user_data["display_name"],
            phone=f"(555) 200-01{index + 1:02d}",
            company=user_data["company"],
            role=user_data["role"],
            preferred_store_id=stores[index % len(stores)].id,
            newsletter_opt_in=index % 2 == 0,
            sms_opt_in=index in (1, 3),
            created_at=MIRROR_REFERENCE_DATE - timedelta(days=120 - index * 11),
        )
        user.set_password(BENCHMARK_PASSWORD)
        db.session.add(user)
        db.session.flush()
        created_users.append(user)
        db.session.add(
            Address(
                user_id=user.id,
                label="Studio",
                recipient=user.display_name,
                line1=f"{100 + index * 11} Benchmark Ave",
                city=["New York", "Brooklyn", "Austin", "Los Angeles"][index],
                state=["NY", "NY", "TX", "CA"][index],
                zip_code=["10001", "11217", "78701", "90013"][index],
                phone=user.phone,
                is_default=True,
            )
        )

    db.session.flush()

    alice, bob, carol, david = created_users
    wishlist_map = {
        alice.id: ["benq-colorpro-32-pd3225u-monitor", "fujifilm-northlight-x-t5-mirrorless-camera", "aputure-storm-300x-bi-color-led", "sandisk-rugged-studio-ssd-4tb"],
        bob.id: ["blackmagic-scout-6k-pro-cinema-camera", "dji-airframe-4s-fly-more-drone", "atomos-ninja-creator-monitor-5", "rode-wireless-creator-duo"],
        carol.id: ["shure-mvx2-usb-stream-mic", "sennheiser-hd-490-pro-reference-headphones", "apple-creatorbook-air-15-laptop"],
        david.id: ["apple-creatorbook-14-m3-pro-laptop", "benq-sw272u-photo-monitor", "epson-p900-fine-art-photo-printer"],
    }
    compare_map = {
        alice.id: ["sony-aurora-a7x-mirrorless-camera", "canon-orbit-r6-mark-ii-mirrorless-camera", "fujifilm-northlight-x-t5-mirrorless-camera"],
        bob.id: ["blackmagic-scout-6k-pro-cinema-camera", "sony-fx30-studio-cinema-camera", "canon-c70-motion-cinema-camera"],
        carol.id: ["rode-wireless-creator-duo", "dji-mic-air-2tx-kit", "shure-mvx2-usb-stream-mic"],
        david.id: ["apple-creatorbook-14-m3-pro-laptop", "dell-precision-edge-16-laptop", "asus-proart-studio-13-oled-laptop"],
    }
    cart_map = {
        alice.id: [("sony-aurora-a7x-mirrorless-camera", 1), ("sigma-artline-24-70mm-f-2-8-dg-dn-lens", 1)],
        bob.id: [("blackmagic-scout-6k-pro-cinema-camera", 1), ("atomos-ninja-creator-monitor-5", 1), ("sandisk-pro-cinema-cfexpress-type-b-512gb-card", 2)],
        carol.id: [("shure-mvx2-usb-stream-mic", 1), ("sennheiser-profile-usb-mic", 1)],
        david.id: [("benq-colorpro-32-pd3225u-monitor", 1), ("sandisk-rugged-studio-ssd-4tb", 1)],
    }
    reservation_map = {
        alice.id: ("fujifilm-northlight-x-t5-mirrorless-camera", stores[0].id),
        bob.id: ("blackmagic-scout-6k-pro-cinema-camera", stores[4].id),
        carol.id: ("rode-wireless-creator-duo", stores[1].id),
        david.id: ("benq-colorpro-32-pd3225u-monitor", stores[5].id),
    }

    for user_id, slugs in wishlist_map.items():
        for slug in slugs:
            db.session.add(WishlistItem(user_id=user_id, product_id=products[slug].id, created_at=MIRROR_REFERENCE_DATE - timedelta(days=(products[slug].id % 40))))
    for user_id, slugs in compare_map.items():
        for slug in slugs:
            db.session.add(CompareItem(user_id=user_id, product_id=products[slug].id, created_at=MIRROR_REFERENCE_DATE - timedelta(days=(products[slug].id % 25))))
    for user_id, entries in cart_map.items():
        for slug, quantity in entries:
            db.session.add(CartItem(user_id=user_id, product_id=products[slug].id, quantity=quantity, added_at=MIRROR_REFERENCE_DATE - timedelta(days=(products[slug].id % 10))))
    for user_id, (slug, store_id) in reservation_map.items():
        db.session.add(
            StoreReservation(
                user_id=user_id,
                store_id=store_id,
                product_id=products[slug].id,
                quantity=1,
                status="Reserved",
                pickup_window="Ready tomorrow after 11:00",
                created_at=MIRROR_REFERENCE_DATE - timedelta(days=3 + (products[slug].id % 4)),
            )
        )

    order_defs = [
        (alice, "BH-20260402-0101", "Delivered", "Ship to address", ["canon-orbit-r6-mark-ii-mirrorless-camera", "canon-rf-24-105mm-f-4l-is-lens"], 18.50, 221.73, "Delivered to Brooklyn studio"),
        (alice, "BH-20260314-0102", "Delivered", "Store pickup", ["peak-design-everyday-sling-10l"], 0.00, 13.22, "Picked up at NYC SuperStore"),
        (bob, "BH-20260409-0201", "Delivered", "Ship to address", ["sony-fx30-studio-cinema-camera", "atomos-ninja-creator-monitor-5", "sandisk-pro-cinema-cfexpress-type-b-512gb-card"], 24.95, 311.42, "Delivered to Studio Meridian"),
        (carol, "BH-20260330-0301", "Delivered", "Ship to address", ["rode-wireless-creator-duo", "sennheiser-hd-490-pro-reference-headphones"], 0.00, 61.11, "Delivered to Signal Audio"),
        (david, "BH-20260411-0401", "Processing", "Store pickup", ["apple-creatorbook-14-m3-pro-laptop", "benq-colorpro-32-pd3225u-monitor"], 0.00, 321.63, "Awaiting pickup at Chicago Pro Counter"),
    ]
    for user, order_number, status, fulfillment, slugs, shipping, tax, note in order_defs:
        order = Order(
            user_id=user.id,
            order_number=order_number,
            status=status,
            fulfillment=fulfillment,
            payment_label="Demo Visa ending in 4242",
            shipping=shipping,
            tax=round(tax, 2),
            note=note,
            created_at=MIRROR_REFERENCE_DATE - timedelta(days=1 + len(order_number)),
        )
        db.session.add(order)
        db.session.flush()
        subtotal = 0
        for slug in slugs:
            product = products[slug]
            subtotal += product.display_price
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    image_path=product.main_image,
                    quantity=1,
                    price=product.display_price,
                    variant_label="Standard",
                )
            )
        order.subtotal = round(subtotal, 2)
        order.total = round(order.subtotal + order.shipping + order.tax, 2)

    db.session.commit()


def copy_instance_to_seed(base_dir: str) -> None:
    source = Path(base_dir) / "instance" / "bh_photo.db"
    target_dir = Path(base_dir) / "instance_seed"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target_dir / "bh_photo.db")
