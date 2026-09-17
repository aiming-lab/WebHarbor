"""Deterministic shipping rules shared by the FedEx mirror and its verifiers.

Every value a task can ask about — zone, quoted price, delivery commitment, and
the initial tracking timeline of a newly created shipment — is computed here from
one implementation. The application renders these values and the verifiers
recompute them from the supplied initial database, so the graded truth is never
duplicated as a literal constant in two places.

Inputs that vary per shipment (service rates, origin and destination states,
weight, package type) are read from the seeded ``service_levels`` rows by the
caller; this module only holds the fixed rules of the local demo.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Iterable

# The demo environment has a fixed "today" so that created shipments, their
# invoices and their timelines are reproducible across resets and rebuilds.
DEMO_SHIP_DATE = "2026-06-04"
DEMO_INVOICE_DUE_DATE = "2026-06-18"

# Package surcharges in demo dollars. An unlisted type falls back to
# DEFAULT_PACKAGE_FEE so the quote never depends on an unbounded input.
PACKAGE_FEES = {"Envelope": 0.0, "Box": 8.0, "Tube": 10.0, "Freight pallet": 48.0}
DEFAULT_PACKAGE_FEE = 6.0

WEST_REGION = frozenset({"CA", "WA", "OR", "AZ", "CO"})
EAST_REGION = frozenset({"NY", "MA", "PA", "FL", "GA", "NC", "VA"})
CENTRAL_REGION = frozenset({"TX", "IL", "OH", "MI"})

# Delivery commitment per service slug: (business days from the ship date,
# commitment time of day). Ranges published by the service card use their upper
# bound so the estimate is a single deterministic value.
DELIVERY_COMMITMENTS = {
    "priority-overnight": (1, "10:30 AM"),
    "standard-overnight": (1, "8:00 PM"),
    "fedex-2day": (2, "4:30 PM"),
    "ground-home": (5, "8:00 PM"),
    "freight-economy": (6, "5:00 PM"),
}
DEFAULT_COMMITMENT = (5, "8:00 PM")

LABEL_CREATED_STATUS = "Label created"
LABEL_CREATED_SUMMARY = "Shipment information sent to local FedEx demo systems."
LABEL_CREATED_DETAILS = "Shipment information sent to the local demo network."
DEMO_SHIPMENT_LABEL = "Local demo shipment"

# Identifier allocation. Every generated identifier is derived from the highest
# value already in use for that identifier family, so removing a row can never
# make the next allocation collide with a row that still exists. The application
# and the verifiers both call these planners, so a graded expectation is computed
# by the same rule that produced the stored value.
SHIPMENT_CODE_PATTERN = r"SH-(\d+)"
TRACKING_NUMBER_PATTERN = r"FDX(\d+)"
INVOICE_NUMBER_PATTERN = r"INV-(\d+)"
PICKUP_CODE_PATTERN = r"PU-(\d+)"
ACCOUNT_NUMBER_PATTERN = r"5100(\d+)"

SHIPMENT_CODE_BASE = 260000
TRACKING_NUMBER_BASE = 260000000
ACCOUNT_NUMBER_WIDTH = 5
PICKUP_CODE_WIDTH = 4
TRACKING_NUMBER_WIDTH = 9


def identifier_numbers(values: Iterable[str | None], pattern: str) -> set[int]:
    """Return every numeric identifier already used by `values`."""
    numbers: set[int] = set()
    for value in values:
        match = re.fullmatch(pattern, str(value or ""))
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def next_identifier(existing: Iterable[int], preferred: int | None = None) -> int:
    """Return a free identifier number.

    `preferred` is used when nothing already occupies it, which keeps related
    identifiers aligned (the shipment, tracking and invoice numbers of one
    shipment). Otherwise the value above the highest in use is returned, which is
    free by construction. Freeness is the only requirement: the seeded guest
    tracking records occupy a higher block than the shipment-linked records, so a
    candidate must not be rejected merely for being below the highest value.
    """
    used = set(existing)
    if preferred is not None and preferred not in used:
        return preferred
    candidate = max(used, default=0) + 1
    while candidate in used:
        candidate += 1
    return candidate


def format_shipment_code(number: int) -> str:
    return f"SH-{number}"


def format_invoice_number(number: int) -> str:
    return f"INV-{number}"


def format_tracking_number(number: int) -> str:
    return f"FDX{number:0{TRACKING_NUMBER_WIDTH}d}"


def format_pickup_code(number: int) -> str:
    return f"PU-{number:0{PICKUP_CODE_WIDTH}d}"


def format_account_number(number: int) -> str:
    return f"5100{number:0{ACCOUNT_NUMBER_WIDTH}d}"


def plan_shipment_identifiers(shipment_codes: Iterable[str | None],
                              tracking_numbers: Iterable[str | None],
                              invoice_numbers: Iterable[str | None]) -> tuple[str, str, str]:
    """Return the (shipment code, tracking number, invoice number) for a new shipment."""
    shipment_number = next_identifier(identifier_numbers(shipment_codes, SHIPMENT_CODE_PATTERN))
    ordinal = shipment_number - SHIPMENT_CODE_BASE
    if ordinal < 1:
        ordinal = 1
    tracking_number = next_identifier(
        identifier_numbers(tracking_numbers, TRACKING_NUMBER_PATTERN),
        preferred=TRACKING_NUMBER_BASE + ordinal,
    )
    invoice_number = next_identifier(
        identifier_numbers(invoice_numbers, INVOICE_NUMBER_PATTERN),
        preferred=shipment_number,
    )
    return (format_shipment_code(shipment_number), format_tracking_number(tracking_number),
            format_invoice_number(invoice_number))


def plan_pickup_code(confirmation_codes: Iterable[str | None]) -> str:
    """Return the confirmation code for a new pickup request."""
    return format_pickup_code(next_identifier(identifier_numbers(confirmation_codes, PICKUP_CODE_PATTERN)))


def plan_account_number(account_numbers: Iterable[str | None]) -> str:
    """Return the account number for a newly registered user."""
    return format_account_number(next_identifier(identifier_numbers(account_numbers, ACCOUNT_NUMBER_PATTERN)))


def shipment_zone(origin_state: str, destination_state: str) -> int:
    """Return the demo zone for a state pair: 1, 2, or 4."""
    if origin_state == destination_state:
        return 1
    for region in (WEST_REGION, EAST_REGION, CENTRAL_REGION):
        if origin_state in region and destination_state in region:
            return 2
    return 4


def package_fee(package_type: str) -> float:
    return PACKAGE_FEES.get(package_type, DEFAULT_PACKAGE_FEE)


def quote_price(base_rate: float, per_lb_rate: float, zone_surcharge: float,
                weight_lb: float, package_type: str, zone: int) -> float:
    """Return the displayed demo price for one service level."""
    total = base_rate + per_lb_rate * weight_lb + zone_surcharge * zone + package_fee(package_type)
    return round(total, 2)


def parse_demo_date(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def format_demo_date(value: date) -> str:
    return value.isoformat()


def add_business_days(start: str, business_days: int) -> str:
    """Return the ISO date `business_days` weekdays after `start`."""
    current = parse_demo_date(start)
    added = 0
    while added < business_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return format_demo_date(current)


def delivery_estimate(service_slug: str, ship_date: str = DEMO_SHIP_DATE) -> str:
    """Return the Current ETA text shown for a newly created shipment."""
    business_days, commitment_time = DELIVERY_COMMITMENTS.get(service_slug, DEFAULT_COMMITMENT)
    return f"{add_business_days(ship_date, business_days)} by {commitment_time}"


def initial_timeline(origin_city: str, origin_state: str,
                     ship_date: str = DEMO_SHIP_DATE) -> list[dict[str, object]]:
    """Return the timeline of a shipment that has only had a label created.

    A created shipment has not been handed to a courier yet, so the timeline
    contains exactly the label-created scan. This keeps the stored status, the
    latest scan and the visible timeline consistent with each other.
    """
    return [
        {
            "sequence": 1,
            "event_time": f"{ship_date} 09:00",
            "location_label": f"{origin_city}, {origin_state}",
            "status_label": LABEL_CREATED_STATUS,
            "details": LABEL_CREATED_DETAILS,
        }
    ]
