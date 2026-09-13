#!/usr/bin/env python3
"""Deterministic seed data for the FedEx mirror.

The seed is a pure function of this tracked source: running it twice produces
byte-identical databases, which is what lets the container build generate
`instance_seed/fedex.db` instead of shipping an opaque binary in the asset
bundle. Benchmark-user password hashes therefore use a fixed per-account salt,
while accounts registered at runtime still get a random salt.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

# The generator must always build this checkout's canonical database. `app`
# derives its engine URI from FEDEX_DATABASE_URI, while rebuild_seed_database()
# copies from DB_PATH, so an ambient URI (for example one exported by a test
# harness) would make the engine write somewhere else and the copy fail. Pin the
# URI before `app` is imported, then assert that the two paths agree.
_SEED_DB_PATH = Path(__file__).resolve().parent / "instance" / "fedex.db"
os.environ["FEDEX_DATABASE_URI"] = f"sqlite:///{_SEED_DB_PATH}"

from app import (  # noqa: E402
    BASE_DIR,
    DB_PATH,
    DEMO_PASSWORD,
    INSTANCE_DIR,
    Claim,
    Invoice,
    Location,
    PickupRequest,
    PickupSlot,
    SearchLog,
    SeedMetadata,
    ServiceLevel,
    Shipment,
    SupportArticle,
    TrackingEvent,
    TrackingRecord,
    User,
    app,
    db,
    dumps_json,
)
from sqlalchemy import func  # noqa: E402
from support_content import SUPPORT_CONTENT, article  # noqa: E402

if DB_PATH != _SEED_DB_PATH:
    raise RuntimeError(
        f"seed generator path mismatch: app DB_PATH={DB_PATH} pinned={_SEED_DB_PATH}")

INSTANCE_SEED_DIR = BASE_DIR / "instance_seed"
INSTANCE_SEED_DB = INSTANCE_SEED_DIR / "fedex.db"
STATIC_DIR = BASE_DIR / "static"
EXTERNAL_CACHE_DIR = STATIC_DIR / "external_cache"

# Version marker stored in the seed itself so a verifier can reject a database
# that was built by different code instead of grading it silently.
SEED_SCHEMA_VERSION = "fedex-source-v2"

# Row counts the finished seed must contain. A seed that does not match these
# exactly is rejected rather than shipped, so a partial build cannot become the
# authoritative state for grading.
EXPECTED_COUNTS = {
    "users": 4,
    "service_levels": 5,
    "locations": 15,
    "pickup_slots": 45,
    "pickup_requests": 8,
    "shipments": 60,
    "tracking_records": 72,
    "tracking_events": 360,
    "invoices": 60,
    "claims": 12,
    "support_articles": 18,
    "search_logs": 3,
    "seed_metadata": 1,
}

BENCHMARK_USERS = [
    {
        "email": "alice.j@test.com",
        "first_name": "Alice",
        "last_name": "Johnson",
        "phone": "206-555-0140",
        "company": "North Ridge Studio",
        "city": "Seattle",
        "state": "WA",
        "zip_code": "98101",
        "account_number": "510000001",
        "preferred_location_slug": "seattle-downtown-wa",
        "invoicing_email": "billing+alice@test.com",
    },
    {
        "email": "bob.c@test.com",
        "first_name": "Bob",
        "last_name": "Carter",
        "phone": "404-555-0148",
        "company": "Peachtree Parts Co.",
        "city": "Atlanta",
        "state": "GA",
        "zip_code": "30303",
        "account_number": "510000002",
        "preferred_location_slug": "atlanta-midtown-ga",
        "invoicing_email": "billing+bob@test.com",
    },
    {
        "email": "carol.d@test.com",
        "first_name": "Carol",
        "last_name": "Diaz",
        "phone": "305-555-0116",
        "company": "South Bay Labs",
        "city": "Miami",
        "state": "FL",
        "zip_code": "33131",
        "account_number": "510000003",
        "preferred_location_slug": "miami-brickell-fl",
        "invoicing_email": "billing+carol@test.com",
    },
    {
        "email": "david.k@test.com",
        "first_name": "David",
        "last_name": "Kim",
        "phone": "312-555-0157",
        "company": "Lakefront Supply",
        "city": "Chicago",
        "state": "IL",
        "zip_code": "60601",
        "account_number": "510000004",
        "preferred_location_slug": "chicago-loop-il",
        "invoicing_email": "billing+david@test.com",
    },
]

SERVICE_LEVELS = [
    {
        "slug": "priority-overnight",
        "name": "FedEx Priority Overnight",
        "summary": "Early next-business-day delivery for urgent demo parcels.",
        "speed_label": "Next business day by 10:30 AM",
        "base_rate": 48.0,
        "per_lb_rate": 1.95,
        "zone_surcharge": 3.4,
        "weekend_delivery": True,
        "money_back_label": "Money-back demo guarantee",
        "sort_order": 1,
    },
    {
        "slug": "standard-overnight",
        "name": "FedEx Standard Overnight",
        "summary": "Reliable overnight delivery with evening commitment.",
        "speed_label": "Next business day by 8:00 PM",
        "base_rate": 34.0,
        "per_lb_rate": 1.65,
        "zone_surcharge": 2.8,
        "weekend_delivery": False,
        "money_back_label": "Priority hold-at-location available",
        "sort_order": 2,
    },
    {
        "slug": "fedex-2day",
        "name": "FedEx 2Day",
        "summary": "Two-day shipping for mid-priority demo deliveries.",
        "speed_label": "2 business days by 4:30 PM",
        "base_rate": 22.0,
        "per_lb_rate": 1.3,
        "zone_surcharge": 2.2,
        "weekend_delivery": False,
        "money_back_label": "Saturday delivery on select lanes",
        "sort_order": 3,
    },
    {
        "slug": "ground-home",
        "name": "FedEx Ground Home Delivery",
        "summary": "Residential ground shipping with delivery manager style updates.",
        "speed_label": "1 to 5 business days",
        "base_rate": 15.0,
        "per_lb_rate": 0.95,
        "zone_surcharge": 1.7,
        "weekend_delivery": True,
        "money_back_label": "Pickup and drop-off routing supported",
        "sort_order": 4,
    },
    {
        "slug": "freight-economy",
        "name": "FedEx Freight Economy",
        "summary": "Less-than-truckload demo freight with pallet support.",
        "speed_label": "3 to 6 business days",
        "base_rate": 96.0,
        "per_lb_rate": 2.45,
        "zone_surcharge": 4.5,
        "weekend_delivery": False,
        "money_back_label": "Liftgate service optional",
        "sort_order": 5,
    },
]

LOCATION_DATA = [
    ("Seattle Downtown Ship Center", "seattle-downtown-wa", "Seattle", "WA", "1401 4th Ave", "206-555-0140", "Ship Center", "7:00 AM - 9:00 PM", ["Drop off", "Hold at location", "Packing help"], ["Parking garage", "Print station"], "Late pickup until 7:30 PM"),
    ("Bellevue Office Print & Ship", "bellevue-office-wa", "Bellevue", "WA", "500 Bellevue Way NE", "425-555-0132", "Office Print & Ship", "8:00 AM - 8:00 PM", ["Drop off", "Passport photo", "Returns"], ["Copy center", "Metered street parking"], "Small parcel cutoff 6:45 PM"),
    ("Portland River District Ship Center", "portland-river-or", "Portland", "OR", "412 NW Glisan St", "503-555-0150", "Ship Center", "7:30 AM - 8:30 PM", ["Drop off", "Pack and ship", "Ground pickup"], ["Bike racks", "Self-service kiosk"], "Ground trailer closes 6:15 PM"),
    ("San Francisco Market Hub", "san-francisco-market-ca", "San Francisco", "CA", "210 Market St", "415-555-0161", "Ship Center", "7:00 AM - 8:00 PM", ["Express drop off", "Hold at location", "Dangerous goods desk"], ["Lobby lockers", "Wheelchair access"], "Priority Overnight cutoff 6:00 PM"),
    ("Los Angeles Arts District Office", "los-angeles-arts-ca", "Los Angeles", "CA", "777 Alameda St", "213-555-0172", "Office Print & Ship", "8:00 AM - 9:00 PM", ["Print & ship", "Returns", "Package hold"], ["On-site parking", "Photo services"], "Same-day courier handoff 5:30 PM"),
    ("Phoenix Camelback Ground Center", "phoenix-camelback-az", "Phoenix", "AZ", "1900 E Camelback Rd", "602-555-0144", "Ship Center", "7:00 AM - 8:00 PM", ["Ground drop off", "Packaging", "Dry ice acceptance"], ["Drive-up bays", "Truck access"], "Freight dock opens at 9:00 AM"),
    ("Denver Union Station Ship Center", "denver-union-co", "Denver", "CO", "1701 Wynkoop St", "303-555-0180", "Ship Center", "7:00 AM - 8:30 PM", ["Express drop off", "Hold at location", "Saturday pickup"], ["Transit access", "Bike storage"], "Weekend handoff by noon"),
    ("Dallas Arts District Hub", "dallas-arts-tx", "Dallas", "TX", "2200 Ross Ave", "214-555-0192", "Ship Center", "7:00 AM - 9:00 PM", ["Drop off", "Ground pickup", "Freight consult"], ["Loading zone", "Label printer"], "Freight cutoff 4:45 PM"),
    ("Houston Midtown Ship Center", "houston-midtown-tx", "Houston", "TX", "3040 Main St", "713-555-0184", "Ship Center", "7:30 AM - 8:30 PM", ["Express drop off", "Hold at location", "Returns"], ["Covered parking", "Lobby lockers"], "Medical cold-pack prep until 5:00 PM"),
    ("Chicago Loop Ship Center", "chicago-loop-il", "Chicago", "IL", "120 W Jackson Blvd", "312-555-0157", "Ship Center", "7:00 AM - 9:00 PM", ["Drop off", "Pack and ship", "Passport photo"], ["Elevator access", "Copy center"], "Priority cutoff 6:30 PM"),
    ("Atlanta Midtown Ship Center", "atlanta-midtown-ga", "Atlanta", "GA", "880 Peachtree St NE", "404-555-0148", "Ship Center", "7:00 AM - 8:30 PM", ["Express drop off", "Pickup counter", "Ground pickup"], ["Garage parking", "Self-service kiosk"], "Saturday pickup until 11:30 AM"),
    ("Miami Brickell Print & Ship", "miami-brickell-fl", "Miami", "FL", "1200 Brickell Ave", "305-555-0116", "Office Print & Ship", "8:00 AM - 8:00 PM", ["Print & ship", "Returns", "Hold at location"], ["Lobby seating", "Photo services"], "International docs accepted until 5:45 PM"),
    ("Charlotte South End Ship Center", "charlotte-southend-nc", "Charlotte", "NC", "1425 S Tryon St", "704-555-0168", "Ship Center", "7:00 AM - 8:30 PM", ["Drop off", "Packing help", "Ground pickup"], ["Free parking", "Large parcel scale"], "Ground dispatch at 6:00 PM"),
    ("Washington Navy Yard Office", "washington-navy-yard-dc", "Washington", "DC", "50 M St SE", "202-555-0145", "Office Print & Ship", "8:00 AM - 8:00 PM", ["Express drop off", "Returns", "Shipping supplies"], ["Metro access", "Elevator access"], "No freight service"),
    ("Boston Back Bay Ship Center", "boston-back-bay-ma", "Boston", "MA", "699 Boylston St", "617-555-0136", "Ship Center", "7:00 AM - 8:00 PM", ["Drop off", "Hold at location", "Saturday pickup"], ["Bike racks", "Copy center"], "Express cutoff 6:15 PM"),
]

SUPPORT_ARTICLES = [
    ("Track by multiple numbers", "track-multiple-numbers", "Tracking", "Paste several tracking numbers separated by commas or line breaks to monitor multi-piece demo shipments in one view."),
    ("What does shipment exception mean?", "shipment-exception-status", "Tracking", "Review common synthetic exception states such as weather delay, address review, or consignee unavailable."),
    ("How local pickup scheduling works", "demo-pickup-scheduling", "Pickup", "See how this local mirror books a pickup window without creating a real courier request."),
    ("Rate estimate zones explained", "rate-estimate-zones", "Shipping rates", "Understand how the demo calculates zone surcharges between origin and destination states."),
    ("Hold at location workflow", "hold-at-location", "Locations", "Learn when a demo package can stay at a staffed hold location for later collection."),
    ("Freight pallet requirements", "freight-pallet-guidance", "Freight", "Box dimensions, pallet notes, and liftgate reminders for local freight quotes."),
    ("Invoice due dates in the demo", "invoice-due-dates", "Billing", "How synthetic invoice due dates and open balances appear in seeded account history."),
    ("File a missing package claim", "missing-package-claim", "Claims", "What claim stages mean inside this deterministic claims dashboard."),
    ("Proof of delivery and signatures", "proof-of-delivery", "Tracking", "Understand signature-required tracking events and delivery handoff notes."),
    ("Drop-off locations and amenities", "dropoff-location-amenities", "Locations", "Search nearby locations by city, services, and lobby amenities."),
    ("Ground vs overnight services", "ground-vs-overnight", "Shipping rates", "Compare the speed, weekend handling, and rate structure for seeded service levels."),
    ("International paperwork in the demo", "international-paperwork-demo", "Shipping", "Synthetic documentation reminders for customs-style paperwork flows."),
    ("Packaging supplies guide", "packaging-supplies-guide", "Packaging", "Recommended envelope, box, tube, and pallet choices for different product categories."),
    ("Weekend delivery commitments", "weekend-delivery-commitments", "Shipping rates", "See which service levels expose weekend delivery copy in the local mirror."),
    ("Claims status timeline", "claims-status-timeline", "Claims", "Interpret submitted, review, info requested, and closed claim milestones."),
    ("Account invoices export", "account-invoices-export", "Billing", "Where invoicing email and historical billing records appear for seeded users."),
    ("Address correction hold", "address-correction-hold", "Tracking", "Why a package may pause for address clarification in the demo timeline."),
    ("Weather delay guidance", "weather-delay-guidance", "Tracking", "Suggested next steps when the seeded timeline includes weather disruptions."),
]

def deterministic_password_hash(password: str, email: str) -> str:
    """Return a fixed-salt PBKDF2 hash for a benchmark account.

    Werkzeug's default hasher draws a random salt, which would make every rebuild
    of the seed differ in bytes. Benchmark accounts are public demo identities, so
    a stable salt derived from the account email keeps the generated seed
    reproducible. Accounts created through `/register` at runtime still call
    `User.set_password`, which uses a random salt.
    """
    fixed_salt = hashlib.sha1(f"fedex-demo-salt-{email}".encode()).hexdigest()[:8]
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), fixed_salt.encode(), 1000, dklen=32).hex()
    return f"pbkdf2:sha256:1000${fixed_salt}${derived}"


def ensure_dirs() -> None:
    for path in [INSTANCE_DIR, INSTANCE_SEED_DIR, EXTERNAL_CACHE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def service_price(service_slug: str, weight_lb: float, lane_index: int) -> float:
    service = next(item for item in SERVICE_LEVELS if item["slug"] == service_slug)
    zone = 1 + (lane_index % 4)
    package_fee = [0.0, 6.0, 9.5, 18.0, 52.0][lane_index % 5]
    return round(service["base_rate"] + service["per_lb_rate"] * weight_lb + service["zone_surcharge"] * zone + package_fee, 2)


def tracking_timeline(record_id: int, origin_city: str, origin_state: str, destination_city: str, destination_state: str, stage: str) -> list[dict[str, str]]:
    stages = [
        {
            "event_time": "2026-06-01 08:15",
            "location_label": f"{origin_city}, {origin_state}",
            "status_label": "Label created",
            "details": "Shipment information sent to the local demo network.",
        },
        {
            "event_time": "2026-06-01 13:40",
            "location_label": f"{origin_city}, {origin_state}",
            "status_label": "Picked up",
            "details": "Driver completed the scheduled pickup in this local benchmark flow.",
        },
        {
            "event_time": "2026-06-02 05:20",
            "location_label": "Memphis, TN",
            "status_label": "In transit",
            "details": "Package reached the national sort hub used by the demo timeline.",
        },
        {
            "event_time": "2026-06-02 18:05",
            "location_label": f"{destination_city}, {destination_state}",
            "status_label": "At local facility",
            "details": "Shipment arrived at the destination station for final handling.",
        },
    ]
    if stage == "Delivered":
        stages.append(
            {
                "event_time": "2026-06-03 11:02",
                "location_label": f"{destination_city}, {destination_state}",
                "status_label": "Delivered",
                "details": "Delivered to front desk in the local demo environment.",
            }
        )
    elif stage == "Out for delivery":
        stages.append(
            {
                "event_time": "2026-06-03 08:10",
                "location_label": f"{destination_city}, {destination_state}",
                "status_label": "Out for delivery",
                "details": "Courier is en route for final delivery today.",
            }
        )
    elif stage == "Weather delay":
        stages.append(
            {
                "event_time": "2026-06-03 07:35",
                "location_label": f"{destination_city}, {destination_state}",
                "status_label": "Shipment exception",
                "details": "Weather conditions paused the last-mile handoff in this seeded timeline.",
            }
        )
    elif stage == "Address review":
        stages.append(
            {
                "event_time": "2026-06-03 09:25",
                "location_label": f"{destination_city}, {destination_state}",
                "status_label": "Operational delay",
                "details": "Address details are under review before a new delivery attempt.",
            }
        )
    else:
        stages.append(
            {
                "event_time": "2026-06-03 09:00",
                "location_label": f"{destination_city}, {destination_state}",
                "status_label": "In transit",
                "details": "Package is on the final transfer leg toward destination.",
            }
        )
    return [
        {"tracking_record_id": record_id, "sequence": index + 1, **event}
        for index, event in enumerate(stages)
    ]


def stage_copy(stage: str) -> tuple[str, str, str]:
    mapping = {
        "Delivered": (
            "Delivered",
            "Delivered to the recipient in this local demo mirror.",
            "Delivered on 2026-06-03 by 11:02 AM",
        ),
        "Out for delivery": (
            "Out for delivery",
            "Courier is en route for the final handoff.",
            "Expected by 8:00 PM today",
        ),
        "Weather delay": (
            "Shipment exception",
            "Weather conditions affected the final leg of the trip.",
            "Updated delivery date pending weather clearance",
        ),
        "Address review": (
            "Operational delay",
            "Address details are being reviewed before another attempt.",
            "Customer action may be required",
        ),
        "In transit": (
            "In transit",
            "Package is moving through the local network toward destination.",
            "Expected delivery by end of next business day",
        ),
    }
    return mapping[stage]


def seed_database() -> None:
    if ServiceLevel.query.count() > 0:
        # An existing database is left exactly as it is: reseeding in place could
        # silently produce a partial state, so a rebuild must go through
        # rebuild_seed_database(), which starts from an empty file.
        return

    ensure_dirs()

    services: dict[str, ServiceLevel] = {}
    for service in SERVICE_LEVELS:
        row = ServiceLevel(
            slug=service["slug"],
            name=service["name"],
            summary=service["summary"],
            speed_label=service["speed_label"],
            base_rate=service["base_rate"],
            per_lb_rate=service["per_lb_rate"],
            zone_surcharge=service["zone_surcharge"],
            weekend_delivery=service["weekend_delivery"],
            money_back_label=service["money_back_label"],
            sort_order=service["sort_order"],
        )
        db.session.add(row)
        services[row.slug] = row

    locations: list[Location] = []
    for entry in LOCATION_DATA:
        name, slug, city, state, address, phone, location_type, hours, services_list, amenities_list, pickup_note = entry
        row = Location(
            name=name,
            slug=slug,
            city=city,
            state=state,
            address=address,
            phone=phone,
            location_type=location_type,
            hours=hours,
            services_json=dumps_json(services_list),
            amenities_json=dumps_json(amenities_list),
            pickup_note=pickup_note,
        )
        db.session.add(row)
        locations.append(row)

    for title, slug, category, summary in SUPPORT_ARTICLES:
        # Every advertised topic gets real local guidance from the tracked content
        # module; a slug without content raises instead of storing a placeholder.
        content = article(slug, title, category, summary)
        db.session.add(
            SupportArticle(
                title=title,
                slug=slug,
                category=category,
                summary=content["summary"],
                body=content["body"],
                related_topics_json=dumps_json(content["topics"]),
            )
        )

    db.session.flush()

    for index, location in enumerate(locations):
        for slot_index, slot_date in enumerate(["2026-06-05", "2026-06-06", "2026-06-07"]):
            db.session.add(
                PickupSlot(
                    location_id=location.id,
                    slot_date=slot_date,
                    time_window=["9:00 AM - 11:00 AM", "12:30 PM - 2:30 PM", "4:00 PM - 6:00 PM"][slot_index],
                    remaining_capacity=max(3, 12 - ((index + slot_index) % 7)),
                    cutoff_note=[
                        "Book 90 minutes ahead",
                        "Same-day requests close at noon",
                        "Weekend pickup requires staffed counter",
                    ][slot_index],
                )
            )

    db.session.add(SeedMetadata(key="seed_schema_version", value=SEED_SCHEMA_VERSION))
    db.session.commit()


def seed_benchmark_users() -> None:
    if User.query.count() > 0:
        # All four benchmark accounts and their dependent rows are created
        # together. A single missing account is treated as an incomplete seed
        # rather than a reason to skip the rest of the state.
        if User.query.count() != EXPECTED_COUNTS["users"]:
            raise ValueError(
                f"partial benchmark state: {User.query.count()} of {EXPECTED_COUNTS['users']} accounts exist")
        return

    locations = {location.slug: location for location in Location.query.order_by(Location.slug.asc()).all()}
    users: list[User] = []
    for entry in BENCHMARK_USERS:
        user = User(**entry)
        # Fixed-salt hash so a rebuilt seed is byte-identical to the shipped one.
        user.password_hash = deterministic_password_hash(DEMO_PASSWORD, user.email)
        db.session.add(user)
        users.append(user)
    db.session.flush()

    slots = PickupSlot.query.order_by(PickupSlot.slot_date.asc(), PickupSlot.id.asc()).all()
    stages = ["Delivered", "In transit", "Out for delivery", "Weather delay", "Address review"]
    location_list = list(locations.values())

    shipment_counter = 0
    tracking_counter = 0
    for user_index, user in enumerate(users):
        for shipment_index in range(15):
            shipment_counter += 1
            origin = location_list[(user_index * 3 + shipment_index) % len(location_list)]
            destination = location_list[(user_index * 3 + shipment_index + 5) % len(location_list)]
            service = SERVICE_LEVELS[(shipment_index + user_index) % len(SERVICE_LEVELS)]
            package_type = ["Box", "Envelope", "Tube", "Pak", "Freight pallet"][shipment_index % 5]
            weight_lb = round(1.5 + (shipment_index % 6) * 2.75 + user_index * 0.4, 1)
            total_cost = service_price(service["slug"], weight_lb, shipment_counter)
            stage = stages[(shipment_index + user_index) % len(stages)]
            shipment_code = f"SH-{260000 + shipment_counter}"
            tracking_number = f"FDX{260000000 + shipment_counter:09d}"
            invoice_number = f"INV-{260000 + shipment_counter}"

            shipment = Shipment(
                shipment_code=shipment_code,
                tracking_number=tracking_number,
                user_id=user.id,
                service_slug=service["slug"],
                package_type=package_type,
                package_weight=weight_lb,
                origin_city=origin.city,
                origin_state=origin.state,
                destination_city=destination.city,
                destination_state=destination.state,
                recipient_name=["Maya Harper", "Noah Bennett", "Priya Shah", "Leo Kim", "Jules Chen"][shipment_index % 5],
                declared_value=round(80 + shipment_index * 22 + user_index * 18, 2),
                total_cost=total_cost,
                fulfillment_mode=["dropoff", "pickup", "dropbox"][shipment_index % 3],
                pickup_location_slug=origin.slug,
                pickup_window=["", "12:30 PM - 2:30 PM", "4:00 PM - 6:00 PM"][shipment_index % 3],
                status=stage_copy(stage)[0],
                created_on=f"2026-05-{10 + ((shipment_index + user_index) % 18):02d}",
                invoice_number=invoice_number,
                reference_label=[
                    "Demo replacement parts",
                    "Client presentation materials",
                    "Prototype samples",
                    "Signed documents",
                    "Warehouse replenishment",
                ][shipment_index % 5],
            )
            db.session.add(shipment)
            db.session.flush()

            status_stage, status_summary, estimated_delivery = stage_copy(stage)
            tracking = TrackingRecord(
                tracking_number=tracking_number,
                shipment_id=shipment.id,
                user_id=user.id,
                recipient_name=shipment.recipient_name,
                sender_name=user.full_name,
                origin_city=shipment.origin_city,
                origin_state=shipment.origin_state,
                destination_city=shipment.destination_city,
                destination_state=shipment.destination_state,
                service_slug=shipment.service_slug,
                package_type=shipment.package_type,
                weight_lb=shipment.package_weight,
                status_stage=status_stage,
                status_summary=status_summary,
                ship_date=shipment.created_on,
                estimated_delivery=estimated_delivery,
                latest_scan=status_stage,
                package_count=1 + (shipment_index % 3 == 0),
                signature_required=shipment_index % 4 == 0,
                dropoff_location_slug=origin.slug,
            )
            db.session.add(tracking)
            db.session.flush()

            for event in tracking_timeline(
                tracking.id,
                shipment.origin_city,
                shipment.origin_state,
                shipment.destination_city,
                shipment.destination_state,
                stage,
            ):
                db.session.add(TrackingEvent(**event))

            db.session.add(
                Invoice(
                    invoice_number=invoice_number,
                    user_id=user.id,
                    shipment_id=shipment.id,
                    billed_on=shipment.created_on,
                    due_date=f"2026-06-{8 + ((shipment_index + user_index) % 16):02d}",
                    amount=shipment.total_cost,
                    status=["Paid", "Open", "Open", "Processing"][shipment_index % 4],
                )
            )

            if shipment_index in {2, 7, 11}:
                db.session.add(
                    Claim(
                        claim_number=f"CLM-{2600 + shipment_counter}",
                        user_id=user.id,
                        tracking_number=tracking_number,
                        claim_type=["Delay reimbursement", "Damage review", "Missing package"][shipment_index % 3],
                        amount=round(shipment.total_cost * [0.35, 0.55, 0.8][shipment_index % 3], 2),
                        status=["Under review", "Info requested", "Closed"][shipment_index % 3],
                        opened_on=f"2026-06-{2 + ((shipment_index + user_index) % 9):02d}",
                        note="Synthetic claim created for benchmark review flows.",
                    )
                )

        for pickup_index in range(2):
            slot = slots[(user_index * 4 + pickup_index * 3) % len(slots)]
            db.session.add(
                PickupRequest(
                    confirmation_code=f"PU-{2600 + user_index * 10 + pickup_index:04d}",
                    user_id=user.id,
                    location_id=slot.location_id,
                    slot_date=slot.slot_date,
                    time_window=slot.time_window,
                    package_count=pickup_index + 1,
                    status=["Scheduled", "Ready for driver"][pickup_index],
                    created_on=f"2026-06-0{pickup_index + 2}",
                )
            )

    guest_statuses = ["Delivered", "In transit", "Weather delay", "Address review"]
    for extra_index in range(12):
        tracking_counter += 1
        origin = location_list[(extra_index + 2) % len(location_list)]
        destination = location_list[(extra_index + 8) % len(location_list)]
        service = SERVICE_LEVELS[extra_index % len(SERVICE_LEVELS)]
        stage = guest_statuses[extra_index % len(guest_statuses)]
        status_stage, status_summary, estimated_delivery = stage_copy(stage)
        tracking = TrackingRecord(
            tracking_number=f"FDX{260000500 + extra_index:09d}",
            recipient_name=["Avery Stone", "Harper Lee", "Jordan Park", "Taylor Moss"][extra_index % 4],
            sender_name=["Retail Returns", "Warehouse Dock", "Studio Supply", "Medical Lab"][extra_index % 4],
            origin_city=origin.city,
            origin_state=origin.state,
            destination_city=destination.city,
            destination_state=destination.state,
            service_slug=service["slug"],
            package_type=["Box", "Pak", "Envelope", "Tube"][extra_index % 4],
            weight_lb=round(2.2 + extra_index * 0.6, 1),
            status_stage=status_stage,
            status_summary=status_summary,
            ship_date=f"2026-05-{20 + (extra_index % 8):02d}",
            estimated_delivery=estimated_delivery,
            latest_scan=status_stage,
            package_count=1 + (extra_index % 3 == 0),
            signature_required=extra_index % 4 == 0,
            dropoff_location_slug=origin.slug,
        )
        db.session.add(tracking)
        db.session.flush()
        for event in tracking_timeline(
            tracking.id,
            tracking.origin_city,
            tracking.origin_state,
            tracking.destination_city,
            tracking.destination_state,
            stage,
        ):
            db.session.add(TrackingEvent(**event))

    db.session.add_all(
        [
            # Illustrative recent searches only. These rows are never rendered, but
            # they must not restate a task query or a graded answer, so they name
            # topics no task asks about.
            SearchLog(query="box sizes", search_type="support", created_on="2026-06-04"),
            SearchLog(query="holiday hours", search_type="global", created_on="2026-06-04"),
            SearchLog(query="customs forms", search_type="support", created_on="2026-06-04"),
        ]
    )

    db.session.commit()


def validate_seed() -> None:
    """Fail closed unless the seeded database matches the expected shape.

    A partial or stale seed must never become the authoritative state used for
    grading, so the counts and the version marker are checked after seeding and
    any mismatch raises instead of being committed silently.
    """
    tables = {
        "users": User,
        "service_levels": ServiceLevel,
        "locations": Location,
        "pickup_slots": PickupSlot,
        "pickup_requests": PickupRequest,
        "shipments": Shipment,
        "tracking_records": TrackingRecord,
        "tracking_events": TrackingEvent,
        "invoices": Invoice,
        "claims": Claim,
        "support_articles": SupportArticle,
        "search_logs": SearchLog,
    }

    def count(model) -> int:
        # SearchLog declares a column named `query`, so `Model.query` is not the
        # Flask-SQLAlchemy query property for every model here.
        return db.session.query(func.count()).select_from(model).scalar() or 0

    wrong = {name: (expected, count(model))
             for name, model in tables.items()
             for expected in (EXPECTED_COUNTS[name],)
             if count(model) != expected}
    if wrong:
        raise ValueError(f"seeded row counts do not match the contract: {wrong}")

    marker = db.session.get(SeedMetadata, "seed_schema_version")
    if marker is None or marker.value != SEED_SCHEMA_VERSION:
        raise ValueError(
            f"seed version marker is {marker.value if marker else None!r}, expected {SEED_SCHEMA_VERSION!r}")

    orphaned = (TrackingRecord.query.filter(
        TrackingRecord.shipment_id.isnot(None),
        ~TrackingRecord.shipment_id.in_(db.session.query(Shipment.id)),
    ).count())
    if orphaned:
        raise ValueError(f"{orphaned} tracking records reference a missing shipment")

    articles = count(SupportArticle)
    generic = db.session.query(func.count()).select_from(SupportArticle).filter(
        SupportArticle.body.like("%It uses synthetic shipping records, seeded route milestones%")
    ).scalar() or 0
    if articles != len(SUPPORT_CONTENT) or generic != len(SUPPORT_CONTENT):
        raise ValueError(
            f"support content mismatch: articles={articles} "
            f"tracked={len(SUPPORT_CONTENT)} with_disclaimer={generic}")

    if db.session.execute(db.text("PRAGMA foreign_key_check")).fetchall():
        raise ValueError("seeded database violates a declared foreign key")


def rebuild_seed_database() -> None:
    ensure_dirs()
    db.session.remove()
    db.engine.dispose()
    for db_file in [DB_PATH, INSTANCE_SEED_DB]:
        if db_file.exists():
            db_file.unlink()
    db.drop_all()
    db.create_all()
    try:
        seed_database()
        seed_benchmark_users()
        validate_seed()
    except Exception:
        db.session.rollback()
        raise
    db.session.remove()
    shutil.copy2(DB_PATH, INSTANCE_SEED_DB)


def current_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    with app.app_context():
        rebuild_seed_database()
        print(f"seed db -> {INSTANCE_SEED_DB}")
        print(f"md5     -> {current_md5(INSTANCE_SEED_DB)}")
