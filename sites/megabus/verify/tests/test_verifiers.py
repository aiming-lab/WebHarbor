"""Deterministic verifier contract tests for the 21 Megabus tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed sqlite
delta); a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a
wrong answer MUST FAIL; a shortcut (correct answer with homepage-only
navigation) MUST FAIL: every task's required surface is beyond the homepage.
Read-only tasks MUST FAIL on a mutated after-DB; stateful tasks MUST FAIL on
a state-mismatch (no DB delta) and on a wrong delta. Package tampering
(task_id mismatch, off-site URLs, missing screenshots, non-done trajectory)
MUST fail closed.

No LLM: snapshots are seed copies mutated through sqlite, trajectories are
hand-written in the agent_demo/agent.py shape.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (BASE, PASSWORD, RunBuilder, _acquire_seed,  # noqa: E402
                       build_run, copy_db, db_one, mutate_db, noop_run,
                       run_verifier)

STATEFUL = {0, 2, 3, 4, 17, 18, 19}
READ_ONLY = sorted(set(range(21)) - STATEFUL)
CREATED = "2026-09-23 14:30:00.000000"

# seed journey ids used by the stateful fixtures
J_BAL_NY_MORNING = None  # resolved from the seed at fixture build time


def _seed():
    return _acquire_seed()


def _journey_id(db, origin, dest, date, dep):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT id FROM journeys WHERE origin_city_id=? AND dest_city_id=? "
            "AND departure_date=? AND dep_time=?", (origin, dest, date, dep)).fetchone()[0]
    finally:
        con.close()


# ---------------------------------------------------------------- navigation fixtures
def honest_run_00(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 0 honest run: planner -> fare finder -> basket + EMAIL5 -> guest
    checkout -> confirmation. After-DB: one booking (86.97)."""
    seed = _seed()
    root = tmp / "honest_00"
    b = build_run(tmp, "honest_00", "Megabus--0")
    jid = _journey_id(seed, 143, 123, "2026-10-03", "08:35")
    b.step("/journey-planner/journeys?originId=143&destinationId=123&departureDate=2026-10-03&totalPassengers=2", "goto", {})
    b.step("/journey-planner/basket", "click", {"selector": "[data-testid=add-ticket-to-basket]"})
    b.step("/fare-finder", "goto", {})
    b.step("/journey-planner/basket", "goto", {})
    b.fill("/journey-planner/basket", "EMAIL5", "#promo")
    b.step("/journey-planner/basket", "click", {"selector": "button:has-text('Apply')"})
    b.step("/journey-planner/basket", "check", {"selector": "#checkbox-terms"})
    b.step("/journey-planner/basket", "click", {"selector": "[data-testid=basket-pay-button]"},
           url_after="/journey-planner/login")
    b.step("/journey-planner/login", "click", {"selector": "[data-testid=checkout-guest]"},
           url_after="/journey-planner/passenger-details")
    b.fill("/journey-planner/passenger-details", "cousins.trip@example.com", "#email")
    b.step("/journey-planner/passenger-details", "click",
           {"selector": "button:has-text('Continue to payment')"}, url_after="/journey-planner/payment")
    b.step("/journey-planner/payment", "click", {"selector": "button:has-text('Pay $')"},
           url_after="/journey-planner/confirmation/AB12CD")
    b.done("I booked the 8:35am bus and applied code EMAIL5. My order reference is AB12CD "
           "and the total charged was $86.97.", final_path="/journey-planner/confirmation/AB12CD")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO bookings (id, reference, email, last_name, user_id, status, total, "
         "sms_updates, passenger_names, created_at, created_on) VALUES "
         "(9, 'AB12CD', 'cousins.trip@example.com', 'Trip', NULL, 'confirmed', 86.97, 0, "
         "'Cousin Trip', ?, '2026-09-23')", (CREATED,)),
        ("INSERT INTO booking_journeys (id, booking_id, journey_id, passengers, price) "
         "VALUES (9, 9, ?, 2, 87.98)", (jid,)),
    ])
    return root, seed, after


def honest_run_02(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 2 honest run: register Jordan Reyes -> book cheapest BOS->NY ->
    pay as the signed-in account. After-DB: +1 user, +1 booking 38.98."""
    seed = _seed()
    root = tmp / "honest_02"
    b = build_run(tmp, "honest_02", "Megabus--2")
    jid = _journey_id(seed, 94, 123, "2026-10-03", "06:00")
    b.step("/account-management/register", "goto", {})
    b.fill("/account-management/register", "Jordan", "#first_name")
    b.fill("/account-management/register", "Reyes", "#last_name")
    b.fill("/account-management/register", "jordan.reyes@example.com", "#email")
    b.fill("/account-management/register", "BookBus2026!", "#password")
    b.step("/account-management/register", "click", {"selector": "button[type=submit]"},
           url_after="/account-management")
    b.step("/journey-planner/journeys?originId=94&destinationId=123&departureDate=2026-10-03&totalPassengers=1", "goto", {})
    b.step("/journey-planner/basket", "click", {"selector": "[data-testid=add-ticket-to-basket]"})
    b.step("/journey-planner/basket", "goto", {})
    b.step("/journey-planner/basket", "check", {"selector": "#checkbox-terms"})
    b.step("/journey-planner/basket", "click", {"selector": "[data-testid=basket-pay-button]"},
           url_after="/journey-planner/passenger-details")
    b.step("/journey-planner/passenger-details", "click",
           {"selector": "button:has-text('Continue to payment')"}, url_after="/journey-planner/payment")
    b.step("/journey-planner/payment", "click", {"selector": "button:has-text('Pay $')"},
           url_after="/journey-planner/confirmation/CD34EF")
    b.done("Account created for Jordan Reyes. I booked the 6:00am bus; my order reference "
           "is CD34EF and the total was $38.98.", final_path="/journey-planner/confirmation/CD34EF")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO users (id, email, password_hash, first_name, last_name, phone, "
         "newsletter, created_at) VALUES (5, 'jordan.reyes@example.com', "
         "'$2b$12$DBQeVglqWXZOTGSQm.DtRe9DGERTLOmPaYINgAATIiJDGKsNo.mZi', 'Jordan', 'Reyes', "
         "'', 0, ?)", (CREATED,)),
        ("INSERT INTO bookings (id, reference, email, last_name, user_id, status, total, "
         "sms_updates, passenger_names, created_at, created_on) VALUES "
         "(9, 'CD34EF', 'jordan.reyes@example.com', 'Reyes', 5, 'confirmed', 38.98, 0, "
         "'Jordan Reyes', ?, '2026-09-23')", (CREATED,)),
        ("INSERT INTO booking_journeys (id, booking_id, journey_id, passengers, price) "
         "VALUES (9, 9, ?, 1, 34.99)", (jid,)),
    ])
    return root, seed, after


def honest_run_03(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 3 honest run: login bob -> 10-10 PHL->WDC schedule pre-check ->
    manage-booking M2V6YH -> change page -> pick 10-10 17:15 -> confirm.
    After-DB: booking_journeys row moved + total 75.45."""
    seed = _seed()
    root = tmp / "honest_03"
    b = build_run(tmp, "honest_03", "Megabus--3")
    new_jid = _journey_id(seed, 127, 142, "2026-10-10", "17:15")
    b.login("bob.c@test.com")
    b.step("/journey-planner/journeys?originId=127&destinationId=142&departureDate=2026-10-10&totalPassengers=1", "goto", {})
    b.step("/journey-planner/manage-booking", "goto", {})
    b.fill("/journey-planner/manage-booking", "M2V6YH", "#reference")
    b.fill("/journey-planner/manage-booking", "bob.c@test.com", "#email")
    b.step("/journey-planner/manage-booking", "click", {"selector": "button:has-text('Search')"},
           url_after="/journey-planner/manage-booking?ref=M2V6YH")
    b.step("/journey-planner/manage-booking/change?ref=M2V6YH&bj=4", "goto", {})
    b.step("/journey-planner/manage-booking/change?ref=M2V6YH&bj=4", "click",
           {"selector": f"input[value='{new_jid}']"})
    b.step("/journey-planner/manage-booking/change?ref=M2V6YH&bj=4", "click",
           {"selector": "button:has-text('Confirm change')"},
           url_after="/journey-planner/manage-booking?ref=M2V6YH")
    b.done("There is only one afternoon departure from Philadelphia to Washington on "
           "October 10th: 5:15pm. My trip now leaves that day at 5:15pm. There was no "
           "fare difference ($0.00) plus a $7.50 amendment fee, and the booking's new "
           "total shown on the booking page is $75.45.",
           final_path="/journey-planner/manage-booking?ref=M2V6YH")
    after = mutate_db(seed, root / "after.db", [
        ("UPDATE booking_journeys SET journey_id=? WHERE booking_id="
         "(SELECT id FROM bookings WHERE reference='M2V6YH')", (new_jid,)),
        ("UPDATE bookings SET total=75.45 WHERE reference='M2V6YH'", ()),
    ])
    return root, seed, after


def honest_run_04(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 4 honest run: login carol -> tracker NY->TOR 10-04 (5:15pm on time)
    -> account -> manage W9C4FJ -> cancel -> account cancelled list."""
    seed = _seed()
    root = tmp / "honest_04"
    b = build_run(tmp, "honest_04", "Megabus--4")
    b.login("carol.d@test.com")
    b.step("/journey-planner/track", "goto", {})
    b.step("/journey-planner/track", "select_option", {"selector": "#originId", "value": "123"})
    b.step("/journey-planner/track", "select_option", {"selector": "#destinationId", "value": "145"})
    b.step("/journey-planner/track", "fill", {"text": "2026-10-04", "selector": "#departureDate"})
    b.step("/journey-planner/track", "click", {"selector": "button[type=submit]"})
    b.step("/account-management", "goto", {})
    b.step("/journey-planner/manage-booking", "goto", {})
    b.fill("/journey-planner/manage-booking", "W9C4FJ", "#reference")
    b.fill("/journey-planner/manage-booking", "carol.d@test.com", "#email")
    b.step("/journey-planner/manage-booking", "click", {"selector": "button:has-text('Search')"},
           url_after="/journey-planner/manage-booking?ref=W9C4FJ")
    b.step("/journey-planner/manage-booking?ref=W9C4FJ", "click",
           {"selector": "button:has-text('Cancel booking')"},
           url_after="/journey-planner/manage-booking?ref=W9C4FJ")
    b.step("/account-management", "goto", {})
    b.done("The tracker shows her 5:15pm New York to Toronto departure is on time, "
           "not delayed. Booking W9C4FJ was cancelled. A refund credit will be emailed "
           "to you within 5-7 business days. The cancelled booking shows a total of "
           "$84.29 under her past and cancelled trips.",
           final_path="/account-management")
    after = mutate_db(seed, root / "after.db", [
        ("UPDATE bookings SET status='cancelled' WHERE reference='W9C4FJ'", ()),
    ])
    return root, seed, after


def honest_run_17(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 17 honest run: login carol -> profile -> update last name + phone
    -> account -> log out -> log back in -> profile re-check."""
    seed = _seed()
    root = tmp / "honest_17"
    b = build_run(tmp, "honest_17", "Megabus--17")
    b.login("carol.d@test.com")
    b.step("/account-management/profile", "goto", {})
    b.fill("/account-management/profile", "Davies", "#last_name")
    b.fill("/account-management/profile", "555-202-7788", "#phone")
    b.step("/account-management/profile", "click", {"selector": "button[type=submit]"},
           url_after="/account-management")
    b.step("/account-management", "goto", {})
    b.step("/account-management/logout", "goto", {}, url_after="/")
    b.login("carol.d@test.com")
    b.step("/account-management/profile", "goto", {})
    b.done("The account page now shows the name Carol Davies and the phone number "
           "555-202-7788. After signing out and back in, the profile page still "
           "shows the saved details: Carol Davies and 555-202-7788 persisted.",
           final_path="/account-management/profile")
    after = mutate_db(seed, root / "after.db", [
        ("UPDATE users SET last_name='Davies', phone='555-202-7788' WHERE id=3", ()),
    ])
    return root, seed, after


def honest_run_18(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 18 honest run: journeys -> basket -> SAVE20 (fails) -> fare finder
    -> EMAIL5 -> read total. After-DB: one basket row, no booking."""
    seed = _seed()
    root = tmp / "honest_18"
    b = build_run(tmp, "honest_18", "Megabus--18")
    jid = _journey_id(seed, 123, 127, "2026-10-03", "00:00")
    b.step("/journey-planner/journeys?originId=123&destinationId=127&departureDate=2026-10-03&totalPassengers=1", "goto", {})
    b.step("/journey-planner/basket", "click", {"selector": "[data-testid=add-ticket-to-basket]"})
    b.step("/journey-planner/basket", "goto", {})
    b.fill("/journey-planner/basket", "SAVE20", "#promo")
    b.step("/journey-planner/basket", "click", {"selector": "button:has-text('Apply')"})
    b.step("/fare-finder", "goto", {})
    b.step("/fare-finder/search?originId=123", "goto", {})
    b.step("/journey-planner/basket", "goto", {})
    b.fill("/journey-planner/basket", "EMAIL5", "#promo")
    b.step("/journey-planner/basket", "click", {"selector": "button:has-text('Apply')"})
    b.step("/journey-planner/basket", "check", {"selector": "#sms_updates"})
    b.done("SAVE20 was not valid. The advertised code is EMAIL5; after applying it the "
           "basket total before paying is $24.98. The fare finder lists Newark, NJ as "
           "the cheapest destination from New York at $13.50. With text message travel "
           "updates enabled the total would be $25.23.",
           final_path="/journey-planner/basket")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO basket_items (id, basket_token, journey_id, passengers, unit_price) "
         "VALUES (1, 'tok-fixture', ?, 1, 25.99)", (jid,)),
    ])
    return root, seed, after


def honest_run_19(tmp: Path) -> tuple[Path, Path, Path]:
    """Task 19 honest run: TOR->MTL cheapest -> basket + SMS -> guest checkout ->
    confirmation. After-DB: one booking 76.23 with sms_updates=1."""
    seed = _seed()
    root = tmp / "honest_19"
    b = build_run(tmp, "honest_19", "Megabus--19")
    jid = _journey_id(seed, 145, 279, "2026-10-03", "07:00")
    b.step("/journey-planner/journeys?originId=145&destinationId=279&departureDate=2026-10-03&totalPassengers=1", "goto", {})
    b.step("/journey-planner/basket", "click", {"selector": "[data-testid=add-ticket-to-basket]"})
    b.step("/journey-planner/basket", "goto", {})
    b.step("/journey-planner/basket", "check", {"selector": "#checkbox-terms"})
    b.step("/journey-planner/basket", "check", {"selector": "#sms_updates"})
    b.step("/journey-planner/basket", "click", {"selector": "[data-testid=basket-pay-button]"},
           url_after="/journey-planner/login")
    b.step("/journey-planner/login", "click", {"selector": "[data-testid=checkout-guest]"},
           url_after="/journey-planner/passenger-details")
    b.fill("/journey-planner/passenger-details", "yuki.tanaka@example.com", "#email")
    b.step("/journey-planner/passenger-details", "click",
           {"selector": "button:has-text('Continue to payment')"}, url_after="/journey-planner/payment")
    b.step("/journey-planner/payment", "click", {"selector": "button:has-text('Pay $')"},
           url_after="/journey-planner/confirmation/GH56IJ")
    b.done("Order reference GH56IJ. The total charged was $76.23: fare $71.99 plus the "
           "$3.99 booking fee plus the $0.25 SMS fee for travel updates.",
           final_path="/journey-planner/confirmation/GH56IJ")
    after = mutate_db(seed, root / "after.db", [
        ("INSERT INTO bookings (id, reference, email, last_name, user_id, status, total, "
         "sms_updates, passenger_names, created_at, created_on) VALUES "
         "(9, 'GH56IJ', 'yuki.tanaka@example.com', 'Tanaka', NULL, 'confirmed', 76.23, 1, "
         "'Yuki Tanaka', ?, '2026-09-23')", (CREATED,)),
        ("INSERT INTO booking_journeys (id, booking_id, journey_id, passengers, price) "
         "VALUES (9, 9, ?, 1, 71.99)", (jid,)),
    ])
    return root, seed, after


# read-only honest fixtures: (index, steps, final answer)
READ_ONLY_FIXTURES = {
    1: ([
        ("/journey-planner/journeys?originId=123&destinationId=142&departureDate=2026-10-02&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=123&destinationId=142&departureDate=2026-10-01&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=142&destinationId=123&departureDate=2026-10-04&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=142&destinationId=123&departureDate=2026-10-05&totalPassengers=1", "goto", {}),
    ], "The cheapest Friday outbound is $44.99 and the cheapest Sunday return is $49.99; "
       "with the $3.99 booking fee the combined total is $98.97. The outbound I would "
       "take (the 9:30pm departure) travels 4 hours 20 minutes. Leaving Thursday "
       "October 1st would be cheaper at $39.99, and returning Monday October 5th would "
       "also be cheaper at $35.99."),
    5: ([
        ("/journey-planner/manage-booking", "goto", {}),
        ("/journey-planner/manage-booking", "fill", {"text": "H3P8KS", "selector": "#reference"}),
        ("/journey-planner/manage-booking", "fill", {"text": "david.k@test.com", "selector": "#email"}),
        ("/journey-planner/manage-booking", "click", {"selector": "button:has-text('Search')"},
         "/journey-planner/manage-booking?ref=H3P8KS"),
        ("/journey-planner/journeys?originId=142&destinationId=123&departureDate=2026-10-10&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=142&destinationId=123&departureDate=2026-10-08&totalPassengers=1", "goto", {}),
    ], "The booking H3P8KS travels Washington, DC to New York, NY on 2026-10-10 for "
       "3 travelers, total paid $199.21. The booked 06:10 departure leaves earlier than "
       "the 12:10pm service that day, and the schedule shows a per-traveler fare of "
       "$64.99. Its journey details show it boards at Washington Union Station. On the "
       "price ribbon October 7th and October 8th are cheaper at $35.99, so "
       "October 10th is not the cheapest of October 7th through 10th."),
    6: ([
        ("/fare-finder", "goto", {}),
        ("/fare-finder/search?originId=127", "goto", {}),
        ("/journey-planner/journeys?originId=127&destinationId=143&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=127&destinationId=142&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
    ], "The three cheapest destinations from Philadelphia are Baltimore from $15.99, "
       "New York from $19.99 and Washington from $31.98. Baltimore is the fastest to "
       "reach at 1 hour 45 minutes. On October 3rd the cheapest morning departure to "
       "Baltimore is 7:00am at $15.99, boarding at the Peter Pan Bus Lines / Trailways "
       "bus stop at Philadelphia - 1001 Filbert Street. The fare finder's starting fare "
       "for Washington, $31.98, does match that route's cheapest October 3rd fare: they "
       "are the same."),
    7: ([
        ("/route-guides", "goto", {}),
        ("/route-guides/boston-to-new-york-bus", "goto", {}),
        ("/journey-planner/journeys?originId=94&destinationId=123&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=123&destinationId=94&departureDate=2026-10-04&totalPassengers=1", "goto", {}),
    ], "The fastest Boston to New York travel time is 4 hours 20 minutes, with up to "
       "37 services per day. In Boston the bus boards at the Peter Pan stop at South "
       "Station - 700 Atlantic Avenue, and it drops off at the Port Authority Bus "
       "Terminal in New York. On October 3rd the first departure from Boston to New "
       "York is 6:00am at $34.99. The October 4th return from New York to Boston has "
       "19 services with the cheapest fare at $44.99."),
    8: ([
        ("/journey-planner/journeys?originId=123&destinationId=127&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=127&destinationId=123&departureDate=2026-10-04&totalPassengers=1", "goto", {}),
        ("/help", "goto", {}),
        ("/help/traveling-on-the-bus", "goto", {}),
    ], "Outbound on October 3rd the first New York to Philadelphia departure after "
       "6:00am is 6:30am at $25.99; returning October 4th the first Philadelphia to "
       "New York departure after 6:00am is also 6:30am at $25.99. With a general "
       "seating ticket you may bring one piece of luggage and one carry-on bag. "
       "Bicycles are carried only inside a case that does not exceed the luggage "
       "allowance: no more than 62 inches in total dimensions and no more than "
       "50 pounds. If you miss your scheduled departure, no refunds or credits are "
       "given, but reservations can be changed up until 6 hours prior to departure."),
    9: ([
        ("/stops", "goto", {}),
        ("/stops/albany", "goto", {}),
        ("/journey-planner/journeys?originId=89&destinationId=123&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=123&destinationId=89&departureDate=2026-10-04&totalPassengers=1", "goto", {}),
    ], "Adirondack Trailways operates the most Albany stops, serving 3: the stop at "
       "66 Green Street, the Airport stop at 737 Albany Shaker Rd. and the SUNY stop "
       "at 1400 Washington Ave. On October 3rd, 11 services run from Albany to New "
       "York; the first departure at 4:10am costs $32.06 and boards at the Adirondack "
       "Trailways Bus Stop at Albany - 66 Green Street. On October 4th, 23 services "
       "make the return trip to Albany."),
    10: ([
        ("/city-guides", "goto", {}),
        ("/city-guides/toronto", "goto", {}),
        ("/journey-planner/journeys?originId=123&destinationId=145&departureDate=2026-10-04&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=145&destinationId=123&departureDate=2026-10-05&totalPassengers=1", "goto", {}),
    ], "The Toronto guide's top five are the Distillery District, CN Tower, Hockey "
       "Hall of Fame, Toronto Zoo and a ferry ride to the Toronto Islands. On October "
       "4th the cheapest New York to Toronto fare is $80.05 and 3 departures offer "
       "it that day. The October 5th return from Toronto to New York has 2 services "
       "with the cheapest fare at $80.05."),
    11: ([
        ("/journey-planner/journeys?originId=123&destinationId=142&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=127&destinationId=142&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=143&destinationId=142&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
    ], "New York has the earliest first departure after 6am: 6:30am, versus "
       "Philadelphia's 7:00am and Baltimore's 6:50am. That New York ticket costs "
       "$39.99 per traveler and the journey takes 7 hours 10 minutes. That day "
       "New York runs 13 services to Washington, Philadelphia runs 5 services and "
       "Baltimore runs 24 services."),
    12: ([
        ("/journey-planner/journeys?originId=123&destinationId=94&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=94&destinationId=123&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
    ], "15 services run across the day from New York to Boston, 6 of them involve "
       "a connection, and the cheapest fare on the page is $44.99. The two morning "
       "departures that require a connection are 6:30am and 9:00am; the 6:30am one "
       "boards at the Port Authority Bus Terminal in New York. The reverse direction "
       "the same day runs 18 services from Boston to New York, 7 of them with a "
       "connection, and the cheapest fare is $34.99."),
    13: ([
        ("/journey-planner/journeys?originId=123&destinationId=94&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=94&destinationId=123&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
    ], "The 9:00am one-stop journey connects through Providence, with a total travel "
       "time of 5 hours 35 minutes. Its $44.99 fare is the same as the 9:15am direct "
       "service. Its details show it boards at the Port Authority Bus Terminal in "
       "New York, and the connecting leg departs the Providence Bus Terminal at "
       "1 Peter Pan Way. The last departure from Boston to New York that day is "
       "6:30pm at $34.99."),
    14: ([
        ("/journey-planner/track", "goto", {}),
        ("/journey-planner/track", "select_option", {"selector": "#originId", "value": "123"}),
        ("/journey-planner/track", "select_option", {"selector": "#destinationId", "value": "127"}),
        ("/journey-planner/track", "fill", {"text": "2026-10-03", "selector": "#departureDate"}),
        ("/journey-planner/track", "click", {"selector": "button[type=submit]"}),
        ("/journey-planner/track?journeyId=102247484", "goto", {}),
        ("/service-alerts", "goto", {}),
        ("/journey-planner/journeys?originId=123&destinationId=127&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=123&destinationId=127&departureDate=2026-10-04&totalPassengers=1", "goto", {}),
    ], "The 8:45am departure is delayed by 15 minutes and is now expected to arrive "
       "in Philadelphia at 11:00am. Its live position shows the bus has Departed "
       "New York, NY - Port Authority Bus Terminal. The Philadelphia alert moves the "
       "departing stop, so her arrival is not affected. The next departure after "
       "the delayed one is 9:45am at $25.99, and the cheapest October 4th fare if "
       "she rebooks is $25.99."),
    15: ([
        ("/service-alerts", "goto", {}),
        ("/account-management/login", "goto", {}),
        ("/account-management/login", "fill", {"text": "alice.j@test.com", "selector": "#emailAddress"}),
        ("/account-management/login", "fill", {"text": PASSWORD, "selector": "#password"}),
        ("/account-management/login", "click", {"selector": "button[type=submit]"},
         "/account-management"),
        ("/journey-planner/manage-booking?ref=AEG7CWY", "goto", {}),
        ("/journey-planner/manage-booking/change?ref=AEG7CWY&bj=1", "goto", {}),
        ("/journey-planner/journeys?originId=127&destinationId=123&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/journeys?originId=127&destinationId=123&departureDate=2026-10-04&totalPassengers=1", "goto", {}),
    ], "The Philadelphia alert runs from 5 October to 12 October 2026: departing "
       "services board from Platform C at 1001 Filbert Street. Alice's trip departs "
       "Philadelphia on 3 October at 5:30am, so it is not affected — it falls before "
       "the alert window. The change options show she could move the trip to October "
       "6th; the first departure after 6:00am that day is 6:30am at $19.99. On her "
       "route 19 services run on October 3rd, and the cheapest fare if she "
       "rebooked for October 4th would be $25.99."),
    16: ([
        ("/account-management/login", "goto", {}),
        ("/account-management/login", "fill", {"text": "alice.j@test.com", "selector": "#emailAddress"}),
        ("/account-management/login", "fill", {"text": PASSWORD, "selector": "#password"}),
        ("/account-management/login", "click", {"selector": "button[type=submit]"},
         "/account-management"),
        ("/account-management", "goto", {}),
        ("/journey-planner/journeys?originId=127&destinationId=123&departureDate=2026-10-03&totalPassengers=1", "goto", {}),
        ("/journey-planner/manage-booking?ref=AEG7CWY", "goto", {}),
        ("/journey-planner/track", "goto", {}),
        ("/journey-planner/track", "select_option", {"selector": "#originId", "value": "127"}),
        ("/journey-planner/track", "select_option", {"selector": "#destinationId", "value": "123"}),
        ("/journey-planner/track", "fill", {"text": "2026-10-03", "selector": "#departureDate"}),
        ("/journey-planner/track", "click", {"selector": "button[type=submit]"}),
    ], "Alice has two upcoming trips: Philadelphia to New York on 2026-10-03 "
       "departing 5:30am, total $56.22 for 2 travelers, and New York to Washington "
       "on 2026-10-03 departing 9:30am, total $43.98 for 1 traveler. The departure "
       "schedule for Philadelphia to New York that day shows the per-traveler fare "
       "is $25.99. Under Change trip the AEG7CWY booking confirms its total of "
       "$56.22, and the tracker shows her 5:30am departure is on time. The "
       "Philadelphia trip AEG7CWY has the larger total."),
    20: ([
        ("/help", "goto", {}),
        ("/help/traveling-on-the-bus", "goto", {}),
        ("/help/customers-with-special-requirements", "goto", {}),
        ("/journey-planner/journeys?originId=123&destinationId=94&departureDate=2026-09-24&totalPassengers=1", "goto", {}),
    ], "Passengers must show the driver a valid reservation number provided at the "
       "time of purchase, which comes from the confirmation page displayed after "
       "finalizing the purchase (from the 'What do I give the driver when boarding "
       "the bus?' and 'What is my reservation number?' help FAQs). megabus asks you "
       "to arrive at least 15 minutes before departure (from the 'What do I need to "
       "know about boarding the bus?' help FAQ). You are welcome to snack on the "
       "bus, but alcoholic beverages are not permitted (from the 'Can I bring food "
       "on the bus?' help FAQ). On September 24th the first New York to Boston "
       "departure is 6:15am at $53.99, boarding at the Port Authority Bus Terminal."),
}

STATEFUL_FIXTURES = {0: honest_run_00, 2: honest_run_02, 3: honest_run_03,
                     4: honest_run_04, 17: honest_run_17, 18: honest_run_18,
                     19: honest_run_19}


# ---------------------------------------------------------------- tests
@pytest.fixture(scope="module")
def seed():
    return _acquire_seed()


@pytest.fixture()
def tmp(tmp_path):
    return tmp_path


@pytest.mark.parametrize("index", READ_ONLY)
def test_read_only_honest_pass(tmp, seed, index):
    steps, answer = READ_ONLY_FIXTURES[index]
    root = tmp / f"ro_{index:02d}"
    b = build_run(tmp, f"ro_{index:02d}", f"Megabus--{index}")
    for args in steps:
        if len(args) == 3:
            b.step(args[0], args[1], args[2])
        else:
            b.step(args[0], args[1], args[2], url_after=args[3])
    b.done(answer)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    r = run_verifier(index, root)
    assert r["pass"], f"expected honest PASS, got {r}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_stateful_honest_pass(tmp, seed, index):
    root, initial, after = STATEFUL_FIXTURES[index](tmp)
    copy_db(initial, root / "initial.db")
    # after.db was already written by the fixture builder
    r = run_verifier(index, root)
    assert r["pass"], f"expected honest PASS, got {r}"


@pytest.mark.parametrize("index", range(21))
def test_noop_fails(tmp, seed, index):
    root = noop_run(tmp, index)
    r = run_verifier(index, root)
    assert not r["pass"], f"no-op must FAIL for task {index}, got {r}"


@pytest.mark.parametrize("index", READ_ONLY)
def test_wrong_answer_fails(tmp, seed, index):
    steps, _ = READ_ONLY_FIXTURES[index]
    root = tmp / f"wa_{index:02d}"
    b = build_run(tmp, f"wa_{index:02d}", f"Megabus--{index}")
    for args in steps:
        if len(args) == 3:
            b.step(args[0], args[1], args[2])
        else:
            b.step(args[0], args[1], args[2], url_after=args[3])
    b.done("The answer is 42 dollars at 9 o'clock.")
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    r = run_verifier(index, root)
    assert not r["pass"], f"wrong answer must FAIL for task {index}, got {r}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_stateful_wrong_answer_fails(tmp, seed, index):
    root, initial, after = STATEFUL_FIXTURES[index](tmp)
    # honest DB delta but a wrong final answer
    traj = json.loads((root / "trajectory.json").read_text())
    traj["final_answer"] = "I did something and the total was $12.34."
    (root / "trajectory.json").write_text(json.dumps(traj))
    copy_db(initial, root / "initial.db")
    r = run_verifier(index, root)
    assert not r["pass"], f"wrong answer must FAIL for task {index}, got {r}"


@pytest.mark.parametrize("index", range(21))
def test_shortcut_fails(tmp, seed, index):
    """Correct answer, homepage-only navigation: anti knowledge-shortcut gate."""
    root = tmp / f"sc_{index:02d}"
    b = build_run(tmp, f"sc_{index:02d}", f"Megabus--{index}")
    b.step("/", "goto", {})
    if index in READ_ONLY:
        answer = READ_ONLY_FIXTURES[index][1]
        copy_db(seed, root / "initial.db")
        copy_db(seed, root / "after.db")
    else:
        honest_root, initial, after = STATEFUL_FIXTURES[index](tmp)
        answer = json.loads((honest_root / "trajectory.json").read_text())["final_answer"]
        copy_db(seed, root / "initial.db")
        shutil.copy2(after, root / "after.db")
    b.done(answer, final_path="/")
    r = run_verifier(index, root)
    assert not r["pass"], f"shortcut must FAIL for task {index}, got {r}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fails(tmp, seed, index):
    """Agent self-reports success but the DB is unchanged."""
    root, initial, after = STATEFUL_FIXTURES[index](tmp)
    copy_db(initial, root / "initial.db")
    copy_db(seed, root / "after.db")  # unchanged = state mismatch
    r = run_verifier(index, root)
    assert not r["pass"], f"state mismatch must FAIL for task {index}, got {r}"


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fails(tmp, seed, index):
    """The DB changed but not with the task's exact math."""
    root, initial, after = STATEFUL_FIXTURES[index](tmp)
    copy_db(initial, root / "initial.db")
    wrong = mutate_db(seed, root / "after.db", [
        ("UPDATE bookings SET total=total+1.00 WHERE reference='M2V6YH'", ()),
    ])
    r = run_verifier(index, root)
    assert not r["pass"], f"wrong delta must FAIL for task {index}, got {r}"


@pytest.mark.parametrize("index", READ_ONLY)
def test_read_only_mutation_fails(tmp, seed, index):
    """Read-only task on a mutated after-DB: collateral write = FAIL."""
    steps, answer = READ_ONLY_FIXTURES[index]
    root = tmp / f"mut_{index:02d}"
    b = build_run(tmp, f"mut_{index:02d}", f"Megabus--{index}")
    for args in steps:
        if len(args) == 3:
            b.step(args[0], args[1], args[2])
        else:
            b.step(args[0], args[1], args[2], url_after=args[3])
    b.done(answer)
    copy_db(seed, root / "initial.db")
    mutate_db(seed, root / "after.db", [
        ("INSERT INTO newsletter_signups (id, email, created_at) VALUES (1, 'x@y.z', '2026-09-23')", ()),
    ])
    r = run_verifier(index, root)
    assert not r["pass"], f"mutated after-DB must FAIL read-only task {index}, got {r}"


def test_tampered_task_id_fails(tmp, seed):
    root = noop_run(tmp, 0)
    traj = json.loads((root / "trajectory.json").read_text())
    traj["task_id"] = "Megabus--19"
    (root / "trajectory.json").write_text(json.dumps(traj))
    r = run_verifier(0, root)
    assert not r["pass"], r
    assert r.get("reason") in {"trajectory_task_matches", "final_answer_nonempty"}, r


def test_offsite_url_fails(tmp, seed):
    root = tmp / "offsite"
    b = build_run(tmp, "offsite", "Megabus--7")
    b.step("/", "goto", {})
    b.step("https://example.com/route-guides/boston-to-new-york-bus", "goto", {})
    b.step("/route-guides/boston-to-new-york-bus", "goto", {})
    b.done("Fastest 4 hours 20 minutes, up to 37 services, South Station and Port Authority.")
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    r = run_verifier(7, root)
    assert not r["pass"] and r.get("reason") == "all_urls_match_local_origin", r


def test_missing_screenshot_fails(tmp, seed):
    root = tmp / "noshot"
    b = build_run(tmp, "noshot", "Megabus--7")
    b.step("/", "goto", {})
    b.step("/route-guides/boston-to-new-york-bus", "goto", {})
    b.done("Fastest 4 hours 20 minutes, up to 37 services, South Station and Port Authority.")
    (root / "screenshots" / "step_002.png").unlink()
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    r = run_verifier(7, root)
    assert not r["pass"] and r.get("reason") == "screenshots_decode", r


def test_terminated_early_fails(tmp, seed):
    root = tmp / "early"
    b = build_run(tmp, "early", "Megabus--7")
    b.step("/", "goto", {})
    b.step("/route-guides/boston-to-new-york-bus", "goto", {})
    b.done("Fastest 4 hours 20 minutes.", terminated=False, reason="max_steps")
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    r = run_verifier(7, root)
    assert not r["pass"] and r.get("reason") == "trajectory_completed", r


def test_tampered_seed_fails(tmp, seed):
    root = noop_run(tmp, 7)
    mutate_db(seed, root / "initial.db", [
        ("UPDATE journeys SET price=1.00 WHERE id='102247484'", ()),
    ])
    r = run_verifier(7, root)
    assert not r["pass"] and r.get("infra_error"), r
