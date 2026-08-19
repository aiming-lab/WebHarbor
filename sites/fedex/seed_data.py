#!/usr/bin/env python3
"""Deterministic seed data and lightweight local assets for the FedEx mirror."""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

os.environ.setdefault("WEBSYN_SKIP_BOOTSTRAP", "1")

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

INSTANCE_SEED_DIR = BASE_DIR / "instance_seed"
INSTANCE_SEED_DB = INSTANCE_SEED_DIR / "fedex.db"
STATIC_DIR = BASE_DIR / "static"
IMAGE_DIR = STATIC_DIR / "images"
EXTERNAL_CACHE_DIR = STATIC_DIR / "external_cache"

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

PALETTE = [
    ("#4d148c", "#ff6600", "#f4f0fb"),
    ("#5b1aa3", "#ff8f1f", "#f7f2ff"),
    ("#472f92", "#f8c471", "#f5f4fb"),
    ("#3c1053", "#ff7f32", "#fff4eb"),
]


def ensure_dirs() -> None:
    for path in [INSTANCE_DIR, INSTANCE_SEED_DIR, IMAGE_DIR, EXTERNAL_CACHE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_svg(path: Path, title: str, accent: str, secondary: str, background: str, lines: list[str]) -> None:
    bars = "".join(
        f'<rect x="34" y="{88 + i * 18}" width="{220 - i * 18}" height="8" rx="4" fill="{secondary}" opacity="{0.82 - i * 0.08:.2f}"/>'
        for i in range(len(lines))
    )
    labels = "".join(
        f'<text x="42" y="{94 + i * 18}" font-size="10" fill="#1f2937" font-family="Arial">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    path.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200" role="img" aria-label={quoteattr(title)}>
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{background}" />
      <stop offset="100%" stop-color="#ffffff" />
    </linearGradient>
  </defs>
  <rect width="320" height="200" rx="20" fill="url(#g)" />
  <rect x="24" y="24" width="120" height="48" rx="12" fill="{accent}" />
  <rect x="150" y="24" width="146" height="48" rx="12" fill="{secondary}" opacity="0.16" />
  <path d="M58 72h136l28 26H86z" fill="{secondary}" opacity="0.9" />
  <rect x="66" y="112" width="180" height="52" rx="14" fill="#ffffff" stroke="{secondary}" stroke-width="2" />
  {bars}
  {labels}
  <text x="40" y="53" font-size="22" font-weight="700" fill="#ffffff" font-family="Arial">{escape(title)}</text>
</svg>
""",
        encoding="utf-8",
    )


def ensure_visual_assets() -> None:
    write_svg(
        IMAGE_DIR / "hero-tracking.svg",
        "FedEx demo tracker",
        "#4d148c",
        "#ff6600",
        "#f8f4ff",
        ["Track package", "Estimate rates", "Schedule pickup"],
    )
    for index, service in enumerate(SERVICE_LEVELS):
        accent, secondary, background = PALETTE[index % len(PALETTE)]
        write_svg(
            IMAGE_DIR / f"service-{service['slug']}.svg",
            service["name"].replace("FedEx ", ""),
            accent,
            secondary,
            background,
            [service["speed_label"], service["summary"], service["money_back_label"]],
        )
    for index, location in enumerate(LOCATION_DATA):
        accent, secondary, background = PALETTE[index % len(PALETTE)]
        write_svg(
            IMAGE_DIR / f"location-{location[1]}.svg",
            location[2],
            accent,
            secondary,
            background,
            [location[0], location[5], location[6]],
        )


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
        return

    ensure_dirs()
    ensure_visual_assets()

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
            icon_path=f"/static/images/service-{service['slug']}.svg",
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
            image_path=f"/static/images/location-{slug}.svg",
            pickup_note=pickup_note,
        )
        db.session.add(row)
        locations.append(row)

    for title, slug, category, summary in SUPPORT_ARTICLES:
        db.session.add(
            SupportArticle(
                title=title,
                slug=slug,
                category=category,
                summary=summary,
                body=(
                    f"{summary} This page is part of a deterministic local FedEx-style demo. "
                    "It uses synthetic shipping records, seeded route milestones, and fixed support guidance so benchmark agents can practice tracking, billing, and pickup workflows without contacting any live carrier service."
                ),
                related_topics_json=dumps_json([category, "demo workflow", "tracking help"]),
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

    db.session.commit()


def seed_benchmark_users() -> None:
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    locations = {location.slug: location for location in Location.query.order_by(Location.slug.asc()).all()}
    users: list[User] = []
    for entry in BENCHMARK_USERS:
        user = User(**entry)
        user.set_password(DEMO_PASSWORD)
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
            SearchLog(query="weather delay", search_type="support", created_on="2026-06-04"),
            SearchLog(query="FDX260000001", search_type="tracking", created_on="2026-06-04"),
            SearchLog(query="Seattle location", search_type="global", created_on="2026-06-04"),
        ]
    )

    db.session.commit()


def rebuild_seed_database() -> None:
    ensure_dirs()
    db.session.remove()
    db.engine.dispose()
    for db_file in [DB_PATH, INSTANCE_SEED_DB]:
        if db_file.exists():
            db_file.unlink()
    db.drop_all()
    db.create_all()
    seed_database()
    seed_benchmark_users()
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
