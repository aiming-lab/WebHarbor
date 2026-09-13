"""Derive every FedEx task target from a supplied initial SQLite snapshot.

No graded value is written as a literal in the verifiers. Each target is computed
from the database the grader is given, so a seed change moves the expectation
instead of silently grading against stale constants, and an ambiguous target
raises instead of being guessed.

Every function here is deterministic and read-only. `task_ground_truth` is the
single entry point used by `verify_lib`.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

SITE_ROOT = Path(__file__).resolve().parents[1]
if str(SITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SITE_ROOT))

from shipping_rules import (  # noqa: E402
    DELIVERY_COMMITMENTS,
    DEMO_SHIP_DATE,
    plan_pickup_code,
    plan_shipment_identifiers,
    quote_price,
    shipment_zone,
)

SEED_SCHEMA_VERSION = "fedex-source-v2"

EXPECTED_TABLES = frozenset({
    "claims", "invoices", "locations", "pickup_requests", "pickup_slots",
    "search_logs", "seed_metadata", "service_levels", "shipments",
    "support_articles", "tracking_events", "tracking_records", "users",
})

# The seeded vocabulary of shipment statuses is closed, so the "cause" a task asks
# about can be derived from the record's own status instead of being hardcoded.
EXCEPTION_STATUSES = ("Shipment exception", "Operational delay")
STATUS_CAUSE_KEYWORDS = {
    "Shipment exception": ("weather",),
    "Operational delay": ("address",),
    "Delivered": ("delivered",),
    "Out for delivery": ("courier",),
    "In transit": ("transit",),
}
# Statuses that are not the derived one. An answer naming one of these as the
# cause contradicts the record.
COMPETING_CAUSE_KEYWORDS = {
    "Shipment exception": ("address review", "address details"),
    "Operational delay": ("weather",),
}

TASK_COUNT = 18


class GroundTruthError(ValueError):
    """Raised when a target cannot be derived unambiguously."""


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.is_file():
        raise GroundTruthError(f"database snapshot is not a file: {db_path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _all(connection: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, tuple(params)).fetchall()]


def _one(rows: list[dict[str, Any]], description: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise GroundTruthError(f"{description} must be unique; observed {len(rows)} rows")
    return rows[0]


def _extreme(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any],
             maximum: bool, description: str) -> dict[str, Any]:
    if not rows:
        raise GroundTruthError(f"{description} has no candidates")
    value = (max if maximum else min)(key(row) for row in rows)
    return _one([row for row in rows if key(row) == value], description)


def assert_snapshot_contract(db_path: str | Path) -> None:
    """Fail closed unless the snapshot has the expected schema and seed version."""
    connection = _connect(db_path)
    try:
        tables = {row["name"] for row in _all(
            connection, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != EXPECTED_TABLES:
            raise GroundTruthError(
                f"unexpected schema: missing={sorted(EXPECTED_TABLES - tables)} extra={sorted(tables - EXPECTED_TABLES)}")
        markers = _all(connection, "SELECT value FROM seed_metadata WHERE key='seed_schema_version'")
        if len(markers) != 1 or markers[0]["value"] != SEED_SCHEMA_VERSION:
            raise GroundTruthError(
                f"seed version marker is {markers!r}, expected {SEED_SCHEMA_VERSION!r}")
        violations = _all(connection, "PRAGMA foreign_key_check")
        if violations:
            raise GroundTruthError(f"snapshot violates a declared foreign key: {violations[:3]}")
    finally:
        connection.close()


# --------------------------------------------------------------------------- #
# Per-record helpers
# --------------------------------------------------------------------------- #
def tracking_record(connection: sqlite3.Connection, tracking_number: str) -> dict[str, Any]:
    return _one(_all(connection, "SELECT * FROM tracking_records WHERE tracking_number=?", (tracking_number,)),
                f"tracking record {tracking_number}")


def timeline(connection: sqlite3.Connection, record_id: int) -> list[dict[str, Any]]:
    return _all(connection, "SELECT * FROM tracking_events WHERE tracking_record_id=? ORDER BY sequence", (record_id,))


def latest_exception(connection: sqlite3.Connection, tracking_number: str) -> dict[str, Any]:
    record = tracking_record(connection, tracking_number)
    events = timeline(connection, record["id"])
    exceptions = [event for event in events if event["status_label"] in EXCEPTION_STATUSES]
    if not exceptions:
        raise GroundTruthError(f"{tracking_number} has no exception event")
    latest = exceptions[-1]
    city, _, state = str(latest["location_label"]).partition(",")
    return {
        "tracking_number": tracking_number,
        "record_status_stage": record["status_stage"],
        "record_status_summary": record["status_summary"],
        "estimated_delivery": record["estimated_delivery"],
        "event_time": latest["event_time"],
        "event_date": latest["event_time"].split(" ")[0],
        "event_clock": latest["event_time"].split(" ")[1] if " " in latest["event_time"] else "",
        "location_label": latest["location_label"],
        "city": city.strip(),
        "state": state.strip(),
        "status_label": latest["status_label"],
        "details": latest["details"],
        "cause_keywords": STATUS_CAUSE_KEYWORDS[latest["status_label"]],
        "competing_cause_keywords": COMPETING_CAUSE_KEYWORDS.get(latest["status_label"], ()),
    }


def signature_fact(connection: sqlite3.Connection, tracking_number: str) -> dict[str, Any]:
    record = tracking_record(connection, tracking_number)
    required = bool(record["signature_required"])
    return {
        "tracking_number": tracking_number,
        "status_stage": record["status_stage"],
        "signature_required": required,
        "accepted": ("signature is required", "signature required", "requires a signature",
                     "requires signature", "yes") if required else
                    ("no signature", "signature is not required", "signature not required",
                     "does not require a signature", "no"),
        "forbidden": ("no signature", "signature is not required", "signature not required",
                      "does not require a signature", "optional") if required else
                     ("signature is required", "signature required", "requires a signature"),
    }


def location_row(connection: sqlite3.Connection, slug: str) -> dict[str, Any]:
    return _one(_all(connection, "SELECT * FROM locations WHERE slug=?", (slug,)), f"location {slug}")


def support_article(connection: sqlite3.Connection, slug: str) -> dict[str, Any]:
    return _one(_all(connection, "SELECT * FROM support_articles WHERE slug=?", (slug,)),
                f"support article {slug}")


def service_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _all(connection, "SELECT * FROM service_levels ORDER BY sort_order")
    if len(rows) < 2:
        raise GroundTruthError("rate tasks need at least two seeded service levels")
    return rows


def commitment_rank(slug: str) -> tuple[int, int]:
    """Order services by published commitment: (business days, minutes of day)."""
    days, clock = DELIVERY_COMMITMENTS.get(slug)
    if days is None:
        raise GroundTruthError(f"service {slug} has no delivery commitment rule")
    match = re.match(r"(\d{1,2}):(\d{2})\s*([AP])M", clock, re.I)
    if not match:
        raise GroundTruthError(f"cannot parse commitment clock {clock!r}")
    hour = int(match.group(1)) % 12 + (12 if match.group(3).upper() == "P" else 0)
    return days, hour * 60 + int(match.group(2))


def clock_text(value: str) -> str:
    """Normalize '4:45 PM' to the forms an answer may use."""
    return value.strip().casefold()


def quotes_for(connection: sqlite3.Connection, origin_state: str, destination_state: str,
               weight_lb: float, package_type: str) -> list[dict[str, Any]]:
    zone = shipment_zone(origin_state, destination_state)
    rows = []
    for service in service_rows(connection):
        rows.append({
            "slug": service["slug"],
            "name": service["name"],
            "speed_label": service["speed_label"],
            "price": quote_price(service["base_rate"], service["per_lb_rate"],
                                 service["zone_surcharge"], weight_lb, package_type, zone),
            "weekend_delivery": bool(service["weekend_delivery"]),
            "rank": commitment_rank(service["slug"]),
        })
    return rows


def price_forms(price: float) -> tuple[str, ...]:
    """Accepted spellings of a displayed price."""
    exact = f"{price:,.2f}"
    trimmed = f"{price:g}"
    return (f"${exact}", exact, f"${trimmed}", trimmed)


def rate_task(connection: sqlite3.Connection, origin_state: str, destination_state: str,
              weight_lb: float, package_type: str) -> dict[str, Any]:
    quotes = quotes_for(connection, origin_state, destination_state, weight_lb, package_type)
    cheapest = _extreme(quotes, lambda row: row["price"], False, "cheapest service")
    dearest = _extreme(quotes, lambda row: row["price"], True, "most expensive service")
    fastest = _extreme(quotes, lambda row: row["rank"], False, "fastest service")
    prices = [row["price"] for row in quotes]
    if len(set(prices)) != len(prices):
        raise GroundTruthError(f"quote prices are not distinct: {prices}")
    return {
        "origin_state": origin_state,
        "destination_state": destination_state,
        "weight_lb": weight_lb,
        "package_type": package_type,
        "zone": shipment_zone(origin_state, destination_state),
        "quotes": quotes,
        "cheapest": cheapest,
        "most_expensive": dearest,
        "fastest": fastest,
        "fastest_minus_cheapest": round(fastest["price"] - cheapest["price"], 2),
    }


def claim_by_status(connection: sqlite3.Connection, user_email: str, status: str) -> dict[str, Any]:
    rows = _all(connection, """SELECT c.* FROM claims c JOIN users u ON u.id=c.user_id
                               WHERE lower(u.email)=lower(?) AND c.status=?""", (user_email, status))
    return _one(rows, f"{user_email} claim with status {status!r}")


def claim_by_type(connection: sqlite3.Connection, user_email: str, claim_type: str) -> dict[str, Any]:
    rows = _all(connection, """SELECT c.* FROM claims c JOIN users u ON u.id=c.user_id
                               WHERE lower(u.email)=lower(?) AND c.claim_type=?""", (user_email, claim_type))
    return _one(rows, f"{user_email} claim of type {claim_type!r}")


def pickups_with_status(connection: sqlite3.Connection, user_email: str, status: str) -> list[dict[str, Any]]:
    rows = _all(connection, """SELECT p.*, l.name AS location_name, l.slug AS location_slug
                               FROM pickup_requests p JOIN users u ON u.id=p.user_id
                               JOIN locations l ON l.id=p.location_id
                               WHERE lower(u.email)=lower(?) AND p.status=?""", (user_email, status))
    if len(rows) != 1:
        raise GroundTruthError(f"{user_email} must have exactly one {status!r} pickup; observed {len(rows)}")
    return rows


def shipments_with_status(connection: sqlite3.Connection, user_email: str, status: str) -> list[dict[str, Any]]:
    rows = _all(connection, """SELECT s.* FROM shipments s JOIN users u ON u.id=s.user_id
                               WHERE lower(u.email)=lower(?) AND s.status=? ORDER BY s.id""",
                (user_email, status))
    if not rows:
        raise GroundTruthError(f"{user_email} has no shipment with status {status!r}")
    return rows


def delivered_shipment_to(connection: sqlite3.Connection, user_email: str, city: str, state: str) -> dict[str, Any]:
    rows = _all(connection, """SELECT s.*, i.invoice_number AS invoice, i.amount, i.status AS invoice_status
                               FROM shipments s JOIN users u ON u.id=s.user_id
                               JOIN invoices i ON i.shipment_id=s.id
                               WHERE lower(u.email)=lower(?) AND s.destination_city=? AND s.destination_state=?
                                 AND s.status='Delivered'""", (user_email, city, state))
    return _one(rows, f"delivered {user_email} shipment to {city}, {state}")


def exception_guide_facts(connection: sqlite3.Connection) -> dict[str, Any]:
    """Derive task 2's answer from the article body itself."""
    article = support_article(connection, "shipment-exception-status")
    body = article["body"]
    fields = re.search(r"Record the ([a-z ]+) and ([a-z ]+) of the latest exception", body)
    if not fields:
        raise GroundTruthError("the exception guide no longer states which event fields to record")
    status = re.search(r"An ([A-Za-z ]+?)\s+means address details are under review", body)
    if not status:
        raise GroundTruthError("the exception guide no longer names the address-review status")
    return {
        "slug": article["slug"],
        "search_query": "tracking",
        "field_one": fields.group(1).strip(),
        "field_two": fields.group(2).strip(),
        "address_review_status": status.group(1).strip(),
    }


def weather_guide_facts(connection: sqlite3.Connection) -> dict[str, Any]:
    article = support_article(connection, "weather-delay-guidance")
    body = article["body"]
    if "no confirmed delivery date" not in body:
        raise GroundTruthError("the weather guide no longer states the pending-ETA rule")
    return {"slug": article["slug"], "search_query": "delay"}


def earliest_available_slot(connection: sqlite3.Connection, location_slug: str) -> dict[str, Any]:
    location = location_row(connection, location_slug)
    rows = _all(connection, """SELECT * FROM pickup_slots WHERE location_id=? AND remaining_capacity > 0
                               ORDER BY slot_date, id""", (location["id"],))
    if not rows:
        raise GroundTruthError(f"{location_slug} has no slot with remaining capacity")
    return rows[0]


def new_shipment_expectation(connection: sqlite3.Connection, user_email: str, service_slug: str,
                             package_type: str, weight_lb: float, declared_value: float,
                             origin_city: str, origin_state: str, destination_city: str,
                             destination_state: str, recipient_name: str,
                             fulfillment_mode: str) -> dict[str, Any]:
    """Derive the exact rows a correct task-12 run must add."""
    shipment_codes = [row["shipment_code"] for row in _all(connection, "SELECT shipment_code FROM shipments")]
    tracking_numbers = [row["tracking_number"] for row in _all(connection, "SELECT tracking_number FROM tracking_records")]
    invoice_numbers = [row["invoice_number"] for row in _all(connection, "SELECT invoice_number FROM invoices")]
    shipment_code, tracking_number, invoice_number = plan_shipment_identifiers(
        shipment_codes, tracking_numbers, invoice_numbers)
    user = _one(_all(connection, "SELECT * FROM users WHERE lower(email)=lower(?)", (user_email,)),
                f"account {user_email}")
    service = _one(_all(connection, "SELECT * FROM service_levels WHERE slug=?", (service_slug,)),
                   f"service level {service_slug}")
    zone = shipment_zone(origin_state, destination_state)
    total_cost = quote_price(service["base_rate"], service["per_lb_rate"], service["zone_surcharge"],
                             weight_lb, package_type, zone)
    preferred = user["preferred_location_slug"] or ""
    if preferred and not _all(connection, "SELECT id FROM locations WHERE slug=?", (preferred,)):
        preferred = ""
    from shipping_rules import (DEMO_INVOICE_DUE_DATE, DEMO_SHIPMENT_LABEL, LABEL_CREATED_STATUS,
                                LABEL_CREATED_SUMMARY, delivery_estimate, initial_timeline)
    return {
        "shipment_code": shipment_code,
        "tracking_number": tracking_number,
        "invoice_number": invoice_number,
        "user_email": user_email,
        "sender_name": f"{user['first_name']} {user['last_name']}",
        "recipient_name": recipient_name,
        "service_slug": service_slug,
        "package_type": package_type,
        "package_weight": weight_lb,
        "declared_value": declared_value,
        "total_cost": total_cost,
        "zone": zone,
        "origin_city": origin_city,
        "origin_state": origin_state,
        "destination_city": destination_city,
        "destination_state": destination_state,
        "fulfillment_mode": fulfillment_mode,
        "pickup_location_slug": preferred,
        "pickup_window": "",
        "reference_label": DEMO_SHIPMENT_LABEL,
        "package_count": 1,
        "signature_required": 0,
        "status": LABEL_CREATED_STATUS,
        "created_on": DEMO_SHIP_DATE,
        "status_summary": LABEL_CREATED_SUMMARY,
        "estimated_delivery": delivery_estimate(service_slug, DEMO_SHIP_DATE),
        "invoice_billed_on": DEMO_SHIP_DATE,
        "invoice_due_date": DEMO_INVOICE_DUE_DATE,
        "timeline": initial_timeline(origin_city, origin_state, DEMO_SHIP_DATE),
    }


def new_pickup_expectation(connection: sqlite3.Connection, user_email: str, location_slug: str,
                           package_count: int) -> dict[str, Any]:
    """Derive the exact rows a correct task-13 run must add and update."""
    codes = [row["confirmation_code"] for row in _all(connection, "SELECT confirmation_code FROM pickup_requests")]
    slot = earliest_available_slot(connection, location_slug)
    location = location_row(connection, location_slug)
    return {
        "confirmation_code": plan_pickup_code(codes),
        "user_email": user_email,
        "location_slug": location_slug,
        "location_name": location["name"],
        "slot_id": slot["id"],
        "slot_date": slot["slot_date"],
        "time_window": slot["time_window"],
        "package_count": package_count,
        "status": "Scheduled",
        "created_on": DEMO_SHIP_DATE,
        "capacity_before": slot["remaining_capacity"],
        "capacity_after": slot["remaining_capacity"] - 1,
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
BENCHMARK_ACCOUNTS = {
    5: "alice.j@test.com",
    6: "bob.c@test.com",
    7: "carol.d@test.com",
    8: "david.k@test.com",
    12: "alice.j@test.com",
    13: "alice.j@test.com",
    15: "david.k@test.com",
}


def task_ground_truth(db_path: str | Path, task_number: int) -> dict[str, Any]:
    """Return every graded value for one task, derived from `db_path`."""
    if not 0 <= task_number < TASK_COUNT:
        raise GroundTruthError(f"unknown task number {task_number}")
    connection = _connect(db_path)
    try:
        assert_snapshot_contract(db_path)
        if task_number == 0:
            facts = latest_exception(connection, "FDX260000004")
            return {"kind": "tracking_exception", "target": "FDX260000004", **facts}
        if task_number == 1:
            numbers = ("FDX260000001", "FDX260000002", "FDX260000003")
            delivered = [n for n in numbers
                         if tracking_record(connection, n)["status_stage"] == "Delivered"]
            if len(delivered) != 1:
                raise GroundTruthError(f"exactly one of {numbers} must be delivered; observed {delivered}")
            return {"kind": "delivered_comparison", "numbers": numbers, "delivered": delivered[0],
                    "signature": signature_fact(connection, delivered[0])}
        if task_number == 2:
            return {"kind": "exception_guide", **exception_guide_facts(connection)}
        if task_number == 3:
            return {"kind": "rate_cheapest", **rate_task(connection, "CA", "TX", 8.0, "Box")}
        if task_number == 4:
            return {"kind": "rate_fastest_vs_cheapest", **rate_task(connection, "WA", "FL", 4.0, "Envelope")}
        if task_number == 5:
            row = delivered_shipment_to(connection, "alice.j@test.com", "Dallas", "TX")
            return {"kind": "invoice_for_delivered_lane", "account": "alice.j@test.com",
                    "shipment_code": row["shipment_code"], "invoice_number": row["invoice"],
                    "destination_city": row["destination_city"], "destination_state": row["destination_state"]}
        if task_number == 6:
            row = claim_by_status(connection, "bob.c@test.com", "Info requested")
            return {"kind": "claim_by_status", "account": "bob.c@test.com", "status": "Info requested",
                    "status_synonyms": ("info requested", "information requested",
                                        "waiting for more information", "more information"),
                    "claim_number": row["claim_number"], "tracking_number": row["tracking_number"],
                    "claim_type": row["claim_type"]}
        if task_number == 7:
            row = pickups_with_status(connection, "carol.d@test.com", "Ready for driver")[0]
            return {"kind": "pickup_by_status", "account": "carol.d@test.com", "status": "Ready for driver",
                    "confirmation_code": row["confirmation_code"], "time_window": row["time_window"],
                    "location_name": row["location_name"]}
        if task_number == 8:
            rows = shipments_with_status(connection, "david.k@test.com", "Out for delivery")
            return {"kind": "shipment_list_by_status", "account": "david.k@test.com",
                    "status": "Out for delivery",
                    "pairs": tuple((row["shipment_code"], row["destination_city"]) for row in rows)}
        if task_number == 9:
            row = location_row(connection, "dallas-arts-tx")
            return {"kind": "location_note", "slug": row["slug"], "name": row["name"],
                    "search_query": "Ship Center", "note": row["pickup_note"],
                    "competing_notes": tuple(
                        note["cutoff_note"] for note in
                        _all(connection, "SELECT DISTINCT cutoff_note FROM pickup_slots")),
                    "note_times": tuple(re.findall(r"\d{1,2}:\d{2}\s*[AP]M", row["pickup_note"], re.I)),
                    "competing_times": tuple(sorted({
                        time for note in _all(connection, "SELECT DISTINCT cutoff_note FROM pickup_slots")
                        for time in re.findall(r"\d{1,2}:\d{2}\s*[AP]M", note["cutoff_note"], re.I)
                    } - set(re.findall(r"\d{1,2}:\d{2}\s*[AP]M", row["pickup_note"], re.I))))}
        if task_number == 10:
            row = location_row(connection, "miami-brickell-fl")
            return {"kind": "location_note", "slug": row["slug"], "name": row["name"],
                    "search_query": "", "note": row["pickup_note"],
                    "competing_notes": (), "note_times": tuple(
                        re.findall(r"\d{1,2}:\d{2}\s*[AP]M", row["pickup_note"], re.I)),
                    "competing_times": ()}
        if task_number == 11:
            guide = weather_guide_facts(connection)
            facts = latest_exception(connection, "FDX260000004")
            eta = str(facts["estimated_delivery"])
            confirmed = bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b|by \d{1,2}:\d{2}\s*[AP]M", eta)) \
                and "pending" not in eta.casefold()
            return {"kind": "weather_guide_and_eta", **guide, "target": "FDX260000004",
                    "event_date": facts["event_date"], "event_clock": facts["event_clock"],
                    "event_time": facts["event_time"], "estimated_delivery": eta,
                    "eta_confirmed": confirmed}
        if task_number == 12:
            return {"kind": "create_shipment",
                    "expectation": new_shipment_expectation(
                        connection, "alice.j@test.com", "fedex-2day", "Box", 6.0, 240.0,
                        "Seattle", "WA", "Boston", "MA", "Alex Brown", "dropoff")}
        if task_number == 13:
            return {"kind": "schedule_pickup",
                    "expectation": new_pickup_expectation(
                        connection, "alice.j@test.com", "seattle-downtown-wa", 1)}
        if task_number == 14:
            row = location_row(connection, "seattle-downtown-wa")
            opened = re.findall(r"(\d{1,2}:\d{2}\s*[AP]M)\s*-\s*(\d{1,2}:\d{2}\s*[AP]M)", row["hours"], re.I)
            if len(opened) != 1:
                raise GroundTruthError(f"cannot parse posted hours {row['hours']!r}")
            return {"kind": "location_hours", "slug": row["slug"], "name": row["name"],
                    "search_query": "Ship Center", "hours": row["hours"],
                    "opens": opened[0][0], "closes": opened[0][1],
                    "matching_locations": tuple(
                        item["slug"] for item in _all(
                            connection,
                            "SELECT slug,name,location_type FROM locations WHERE name LIKE ? OR location_type LIKE ?",
                            ("%Ship Center%", "%Ship Center%")))}
        if task_number == 15:
            row = claim_by_type(connection, "david.k@test.com", "Damage review")
            return {"kind": "claim_by_type", "account": "david.k@test.com", "claim_type": "Damage review",
                    "claim_type_synonyms": ("damage review", "damage"),
                    "claim_number": row["claim_number"], "tracking_number": row["tracking_number"],
                    "status": row["status"]}
        if task_number == 16:
            record = tracking_record(connection, "FDX260000500")
            events = timeline(connection, record["id"])
            if not events:
                raise GroundTruthError("FDX260000500 has no timeline")
            final = events[-1]
            city, _, state = str(final["location_label"]).partition(",")
            delivered = record["status_stage"] == "Delivered"
            timeline_cities = {
                str(event["location_label"]).partition(",")[0].strip() for event in events}
            seeded_cities = {row["city"] for row in _all(connection, "SELECT city FROM locations")}
            return {"kind": "final_handoff", "target": "FDX260000500", "delivered": delivered,
                    "status_stage": record["status_stage"], "final_status_label": final["status_label"],
                    "final_city": city.strip(), "final_state": state.strip(),
                    "competing_cities": tuple(sorted((timeline_cities | seeded_cities) - {city.strip()}))}
        if task_number == 17:
            return {"kind": "rate_most_expensive", **rate_task(connection, "TX", "FL", 12.0, "Freight pallet")}
        raise GroundTruthError(f"unhandled task number {task_number}")
    finally:
        connection.close()
