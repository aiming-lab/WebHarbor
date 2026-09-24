"""Deterministic verifier contract tests for the 21 Marriott tasks.

Covers, per task: the honest trajectory MUST PASS (read-only tasks against a
clean seed pair; stateful tasks against the seed with the exact allowed sqlite
delta); a no-op run (homepage only, empty answer, clean DB) MUST FAIL; a wrong
answer MUST FAIL; a shortcut (correct answer — and for stateful tasks even the
correct DB delta — with homepage-only navigation) MUST FAIL: every task's
required surface is beyond the homepage. Read-only tasks MUST FAIL on a mutated
after-DB; stateful tasks MUST FAIL on a state-mismatch (no DB delta) and on a
wrong delta. Package tampering (task_id mismatch, off-site URLs, missing
screenshots, non-done trajectory, tampered seed, unavailable DB) MUST fail
closed.

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
from _support import (BASE, PASSWORD, RunBuilder, SEED_DB, _acquire_seed,  # noqa: E402
                      build_run, copy_db, db_one, hotel_id, mutate_db, noop_run,
                      room_id, run_verifier)

STATEFUL = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 16, 17, 18}
READ_ONLY = sorted(set(range(21)) - STATEFUL)
LOGIN = {"alice": "alice.j@test.com", "bob": "bob.c@test.com",
         "carol": "carol.d@test.com", "david": "david.k@test.com"}
CREATED = "2026-09-23 10:00:00.000000"

# frozen marsha codes (seed DB) for the navigation fixtures
M = {"SFOFU": "citizenm-san-francisco-union-square", "CHINO": "the-westin-chicago-river-north",
     "DENMG": "magnolia-hotel-denver-a-tribute-portfolio-hotel",
     "NYCSM": "springhill-suites-new-york-midtown-manhattan-fifth-avenue",
     "NYCMD": "courtyard-new-york-manhattan-times-square", "MCOMA": "courtyard-orlando-downtown",
     "ATLDO": "courtyard-atlanta-downtown", "ATLAR": "ac-hotel-atlanta-downtown",
     "NYCTE": "the-times-square-edition", "SEAZS": "citizenm-seattle-south-lake",
     "LASHH": "residence-inn-las-vegas-hughes-center",
     "LASPR": "springhill-suites-las-vegas-convention-center",
     "MIABR": "citizenm-miami-brickell", "MIAEK": "element-miami-brickell",
     "BOSOX": "moxy-boston-downtown", "CHIJW": "jw-marriott-chicago",
     "NYCZW": "the-westin-new-york-grand-central",
     "NYCLX": "the-lexington-hotel-autograph-collection",
     "NYCRI": "residence-inn-new-york-manhattan-times-square",
     "NYCHA": "residence-inn-new-york-manhattan-midtown-east"}


def hotel_path(marsha: str, tab: str = "overview") -> str:
    return f"/en-us/hotels/{M[marsha]}/{tab}/"


def book_sql(db: Path, conf: str, marsha_hotel: str, room: str, first: str, last: str,
             email: str, checkin: str, checkout: str, nightly: int, total: int,
             points: int = 0, user_email: str | None = None) -> tuple[str, tuple]:
    hid = hotel_id(db, marsha_hotel)
    rid = room_id(db, marsha_hotel, room)
    uid = db_one(db, "SELECT id FROM users WHERE email = ?", (user_email,)) if user_email else None
    return (f"INSERT INTO reservations (confirmation_number, user_id, hotel_id, room_type_id, "
            f"guest_first_name, guest_last_name, guest_email, checkin, checkout, adults, children, "
            f"rooms, nightly_rate, total_rate, points_redeemed, status, special_requests, created_at) "
            f"VALUES ('{conf}', {uid if uid else 'NULL'}, {hid}, {rid}, '{first}', '{last}', "
            f"'{email}', '{checkin}', '{checkout}', {4 if first == 'Dana' else 2 if first in {'Jordan', 'Sam', 'Alex'} else 1}, 0, 1, {nightly}, {total}, {points}, "
            f"'confirmed', NULL, '{CREATED}')", ())


# ---------------------------------------------------------------- navigation fixtures
def honest_steps(index: int, db: Path):
    """[(path, action, params)] navigation for the honest run of task `index`."""
    def login(who):
        return [("fill", LOGIN[who]), ("fill", PASSWORD), ("click-submit", "account")]
    SF = "/search/findHotels.mi?destinationAddress=San%20Francisco%2C%20California&fromDate=11%2F06%2F2026&toDate=11%2F08%2F2026"
    S = {
        0: [("/search/findHotels.mi?destinationAddress=San%20Francisco%2C%20California&minRating=4&sortBy=price&fromDate=11%2F06%2F2026&toDate=11%2F08%2F2026", "goto", {}),
            ("/reservation/availabilitySearch.mi?propertyCode=SFOFU&fromDate=11%2F06%2F2026&toDate=11%2F08%2F2026", "goto", {}),
            (f"/reservation/reservationGateway.mi?propertyCode=SFOFU&roomId={room_id(db, 'citizenM San Francisco Union Square', 'Guest Room, 1 King Bed')}&fromDate=11%2F06%2F2026&toDate=11%2F08%2F2026", "goto", {}),
            ("/reservation/confirmation.mi?confirmationNumber=RT00TEST01", "goto", {})],
        1: [("/sign-in.mi", "fill", LOGIN["alice"]), ("/sign-in.mi", "fill", PASSWORD),
            ("/sign-in.mi", "click-submit", "account"),
            ("/search/findHotels.mi?destinationAddress=Chicago%2C%20Illinois&useRewardsPoints=true&fromDate=10%2F30%2F2026&toDate=10%2F31%2F2026", "goto", {}),
            ("/reservation/availabilitySearch.mi?propertyCode=CHINO&fromDate=10%2F30%2F2026&toDate=10%2F31%2F2026", "goto", {}),
            (f"/reservation/reservationGateway.mi?propertyCode=CHINO&roomId={room_id(db, 'The Westin Chicago River North', 'Guest Room, 1 King Bed')}&fromDate=10%2F30%2F2026&toDate=10%2F31%2F2026", "goto", {}),
            ("/reservation/confirmation.mi?confirmationNumber=RT01TEST01", "goto", {}),
            ("/loyalty/myAccount.mi", "goto", {})],
        2: [("/search/findHotels.mi?destinationAddress=Denver%2C%20Colorado&amenity=Fitness%20Center&sortBy=price&fromDate=12%2F01%2F2026&toDate=12%2F04%2F2026", "goto", {}),
            ("/reservation/availabilitySearch.mi?propertyCode=DENMG&fromDate=12%2F01%2F2026&toDate=12%2F04%2F2026", "goto", {}),
            (f"/reservation/reservationGateway.mi?propertyCode=DENMG&roomId={room_id(db, 'Magnolia Hotel Denver, a Tribute Portfolio Hotel', 'Guest Room, 1 King Bed')}&fromDate=12%2F01%2F2026&toDate=12%2F04%2F2026", "goto", {}),
            ("/reservation/confirmation.mi?confirmationNumber=RT02TEST01", "goto", {})],
        3: [("/search/findHotels.mi?destinationAddress=New%20York%20City%2C%20New%20York&minRating=4&sortBy=price&fromDate=10%2F20%2F2026&toDate=10%2F22%2F2026", "goto", {}),
            ("/reservation/availabilitySearch.mi?propertyCode=NYCSM&fromDate=10%2F20%2F2026&toDate=10%2F22%2F2026", "goto", {}),
            ("/reservation/availabilitySearch.mi?propertyCode=NYCMD&fromDate=10%2F20%2F2026&toDate=10%2F22%2F2026", "goto", {}),
            (f"/reservation/reservationGateway.mi?propertyCode=NYCSM&roomId={room_id(db, 'SpringHill Suites by Marriott New York Midtown Manhattan/Fifth Avenue', 'Guest Room, 1 King Bed')}&fromDate=10%2F20%2F2026&toDate=10%2F22%2F2026", "goto", {}),
            ("/reservation/confirmation.mi?confirmationNumber=RT03TEST01", "goto", {})],
        4: [("/search/findHotels.mi?destinationAddress=Orlando%2C%20Florida&numAdultsPerRoom=4&sortBy=price&fromDate=12%2F18%2F2026&toDate=12%2F21%2F2026", "goto", {}),
            ("/reservation/availabilitySearch.mi?propertyCode=MCOMA&fromDate=12%2F18%2F2026&toDate=12%2F21%2F2026", "goto", {}),
            (f"/reservation/reservationGateway.mi?propertyCode=MCOMA&roomId={room_id(db, 'Courtyard by Marriott Orlando Downtown', 'Guest Room, 2 Double Beds')}&fromDate=12%2F18%2F2026&toDate=12%2F21%2F2026", "goto", {}),
            ("/reservation/confirmation.mi?confirmationNumber=RT04TEST01", "goto", {})],
        5: [("/sign-in.mi", "fill", LOGIN["alice"]), ("/sign-in.mi", "fill", PASSWORD),
            ("/sign-in.mi", "click-submit", "account"),
            ("/loyalty/myAccount.mi", "goto", {}),
            (hotel_path("ATLDO"), "goto", {}),
            ("/reservation/lookupReservation.mi", "fill", "ACCEDGHDDR"),
            ("/reservation/lookupReservation.mi", "click-submit", "lookup"),
            ("/reservation/cancel.mi", "click-submit", "lookup-again")],
        6: [("/sign-in.mi", "fill", LOGIN["david"]), ("/sign-in.mi", "fill", PASSWORD),
            ("/sign-in.mi", "click-submit", "account"),
            ("/loyalty/myAccount.mi", "goto", {}),
            ("/reservation/lookupReservation.mi", "fill", "BRQEBMMFAQ"),
            ("/reservation/lookupReservation.mi", "click-submit", "lookup"),
            ("/reservation/cancel.mi", "click-submit", "lookup-again"),
            ("/reservation/lookupReservation.mi?confirmationNumber=LDNNPGBDCP&lastName=Kim", "goto", {})],
        7: [("/sign-in.mi", "fill", LOGIN["bob"]), ("/sign-in.mi", "fill", PASSWORD),
            ("/sign-in.mi", "click-submit", "account"),
            ("/loyalty/myAccount.mi", "goto", {}),
            (hotel_path("ATLAR"), "goto", {}),
            (hotel_path("ATLAR", "reviews"), "goto", {}),
            ("/reservation/availabilitySearch.mi?propertyCode=ATLAR&fromDate=10%2F18%2F2026&toDate=10%2F20%2F2026", "goto", {}),
            (f"/reservation/reservationGateway.mi?propertyCode=ATLAR&roomId={room_id(db, 'AC Hotel Atlanta Downtown', 'Guest Room, 1 King Bed')}&fromDate=10%2F18%2F2026&toDate=10%2F20%2F2026", "goto", {}),
            ("/reservation/confirmation.mi?confirmationNumber=RT07TEST01", "goto", {})],
        8: [("/sign-in.mi", "fill", LOGIN["bob"]), ("/sign-in.mi", "fill", PASSWORD),
            ("/sign-in.mi", "click-submit", "account"),
            ("/loyalty/myAccount/profile.mi", "goto", {}),
            ("/loyalty/myAccount/profile.mi", "click-submit", "account"),
            ("/logoff", "goto", {}),
            ("/sign-in.mi", "fill", LOGIN["bob"]), ("/sign-in.mi", "fill", PASSWORD),
            ("/sign-in.mi", "click-submit", "account"),
            ("/loyalty/myAccount/profile.mi", "goto", {})],
        9: [("/sign-in.mi", "fill", LOGIN["carol"]), ("/sign-in.mi", "fill", PASSWORD),
            ("/sign-in.mi", "click-submit", "account"),
            ("/loyalty/myAccount/paymentMethods.mi", "goto", {}),
            ("/loyalty/myAccount/paymentMethods.mi", "click-submit", "payments"),
            ("/loyalty/myAccount/profile.mi", "goto", {}),
            ("/loyalty/myAccount/profile.mi", "click-submit", "account")],
        10: [("/sign-in.mi", "fill", LOGIN["alice"]), ("/sign-in.mi", "fill", PASSWORD),
             ("/sign-in.mi", "click-submit", "account"),
             ("/loyalty/myAccount/savedHotels.mi", "goto", {}),
             ("/search/findHotels.mi?destinationAddress=New%20York%20City%2C%20New%20York", "goto", {}),
             (hotel_path("NYCTE"), "goto", {}),
             ("/saved/add/10", "click-submit", "hotel"),
             ("/logoff", "goto", {}),
             ("/sign-in.mi", "fill", LOGIN["alice"]), ("/sign-in.mi", "fill", PASSWORD),
             ("/sign-in.mi", "click-submit", "account"),
             ("/loyalty/myAccount/savedHotels.mi", "goto", {})],
        11: [("/loyalty/createAccount/createAccountPage1.mi", "fill", "Fiona"),
             ("/loyalty/createAccount/createAccountPage1.mi", "fill", "Gray"),
             ("/loyalty/createAccount/createAccountPage1.mi", "fill", "fiona.gray@example.com"),
             ("/loyalty/createAccount/createAccountPage1.mi", "fill", "FionaPass2026!"),
             ("/loyalty/createAccount/createAccountPage1.mi", "click-submit", "account"),
             ("/loyalty/myAccount.mi", "goto", {}),
             ("/search/findHotels.mi?destinationAddress=Seattle%2C%20Washington&sortBy=price", "goto", {}),
             (hotel_path("SEAZS"), "goto", {}),
             ("/saved/add/60", "click-submit", "hotel")],
        12: [("/search/findHotels.mi?destinationAddress=Las%20Vegas%2C%20Nevada&maxPrice=300&minRating=4&sortBy=price&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {}),
             ("/reservation/availabilitySearch.mi?propertyCode=LASHH&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {}),
             ("/reservation/availabilitySearch.mi?propertyCode=LASPR&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {})],
        13: [("/search/findHotels.mi?destinationAddress=Miami%2C%20Florida&useRewardsPoints=true&fromDate=11%2F20%2F2026&toDate=11%2F21%2F2026", "goto", {}),
             (hotel_path("MIABR", "rooms"), "goto", {}),
             (hotel_path("MIABR", "reviews"), "goto", {}),
             (hotel_path("MIAEK", "rooms"), "goto", {}),
             (hotel_path("MIAEK", "reviews"), "goto", {})],
        14: [("/en-us/destinations/united-states/massachusetts/boston.mi", "goto", {}),
             ("/search/findHotels.mi?destinationAddress=Boston%2C%20Massachusetts&sortBy=price&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {}),
             (hotel_path("BOSOX"), "goto", {}),
             (hotel_path("BOSOX", "reviews"), "goto", {}),
             ("/reservation/availabilitySearch.mi?propertyCode=BOSOX&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {}),
             (f"/reservation/reservationGateway.mi?propertyCode=BOSOX&roomId={room_id(db, 'Moxy Boston Downtown', 'Guest Room, 1 King Bed')}&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {}),
             ("/reservation/confirmation.mi?confirmationNumber=RT14TEST01", "goto", {})],
        15: [("/search/findHotels.mi?destinationAddress=Chicago%2C%20Illinois&amenity=Pool&fromDate=11%2F06%2F2026&toDate=11%2F08%2F2026", "goto", {}),
             ("/en-us/hotels/courtyard-chicago-downtown-river-north/overview/", "goto", {}),
             (hotel_path("CHIJW"), "goto", {}),
             ("/en-us/hotels/renaissance-chicago-downtown-hotel/overview/", "goto", {})],
        16: [("/search/findHotels.mi?destinationAddress=New%20York%20City%2C%20New%20York&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {}),
             (hotel_path("NYCZW", "rooms"), "goto", {}),
             (f"/reservation/reservationGateway.mi?propertyCode=NYCZW&roomId={room_id(db, 'The Westin New York Grand Central', 'Premium Suite, 1 King Bed, High Floor')}&fromDate=11%2F13%2F2026&toDate=11%2F15%2F2026", "goto", {}),
             ("/reservation/confirmation.mi?confirmationNumber=RT16TEST01", "goto", {})],
        17: [("/search/findHotels.mi?destinationAddress=New%20York%20City%2C%20New%20York&fromDate=10%2F30%2F2026&toDate=11%2F01%2F2026", "goto", {}),
             (hotel_path("NYCLX", "reviews"), "goto", {}),
             (hotel_path("NYCZW", "reviews"), "goto", {}),
             ("/sign-in.mi", "fill", LOGIN["alice"]), ("/sign-in.mi", "fill", PASSWORD),
             ("/sign-in.mi", "click-submit", "account"),
             (hotel_path("NYCZW"), "goto", {}),
             ("/saved/add/21", "click-submit", "hotel")],
        18: [("/sign-in.mi", "fill", LOGIN["david"]), ("/sign-in.mi", "fill", PASSWORD),
             ("/sign-in.mi", "click-submit", "account"),
             ("/search/findHotels.mi?destinationAddress=New%20York%20City%2C%20New%20York&fromDate=10%2F30%2F2026&toDate=10%2F31%2F2026", "goto", {}),
             (hotel_path("NYCZW", "rooms"), "goto", {}),
             (hotel_path("NYCRI", "rooms"), "goto", {}),
             (f"/reservation/reservationGateway.mi?propertyCode=NYCZW&roomId={room_id(db, 'The Westin New York Grand Central', 'Premium Suite, 1 King Bed, High Floor')}&rateOption=points&fromDate=10%2F30%2F2026&toDate=10%2F31%2F2026", "goto", {}),
             ("/reservation/confirmation.mi?confirmationNumber=RT18TEST01", "goto", {}),
             ("/loyalty/myAccount.mi", "goto", {})],
        19: [("/offers.mi", "goto", {}),
             ("/search/findHotels.mi?destinationAddress=Chicago%2C%20Illinois&brand=CY&fromDate=12%2F05%2F2026&toDate=12%2F06%2F2026", "goto", {}),
             ("/search/findHotels.mi?destinationAddress=Orlando%2C%20Florida&brand=CY&fromDate=12%2F05%2F2026&toDate=12%2F06%2F2026", "goto", {})],
        20: [("/brands.mi", "goto", {}),
             ("/search/findHotels.mi?destinationAddress=New%20York%20City%2C%20New%20York&brand=RZ2&fromDate=12%2F05%2F2026&toDate=12%2F07%2F2026", "goto", {}),
             (hotel_path("NYCHA"), "goto", {}),
             (hotel_path("NYCHA", "rooms"), "goto", {}),
             (hotel_path("NYCRI"), "goto", {}),
             (hotel_path("NYCRI", "rooms"), "goto", {})],
    }
    return S[index]


def apply_steps(builder: RunBuilder, steps):
    for path, action, params in steps:
        if action == "fill":
            builder.fill(path, params, "input")
        elif action == "click-submit":
            after = {"account": "/loyalty/myAccount.mi", "lookup": "/reservation/lookupReservation.mi?confirmationNumber=ACCEDGHDDR&lastName=Johnson",
                     "lookup-again": "/reservation/lookupReservation.mi?confirmationNumber=BRQEBMMFAQ&lastName=Kim",
                     "payments": "/loyalty/myAccount/paymentMethods.mi", "hotel": None}.get(params)
            builder.step(path, "click", {"selector": "button[type=submit]"}, url_after=after)
        else:
            builder.step(path, "goto", {})
    return builder


# ---------------------------------------------------------------- honest answers
def honest_answer(index: int) -> str:
    A = {
        0: "Booked the most affordable rated-4.0+ San Francisco hotel, citizenM San Francisco "
           "Union Square, in its cheapest room type (Guest Room, 1 King Bed) for Jordan Ellis, "
           "11/06/2026 to 11/08/2026. Confirmation number: RT00TEST01. Total shown on the "
           "confirmation page: $340.",
        1: "Lowest nightly points rate in Chicago: The Westin Chicago River North at 19,000 "
           "points per night; booked its cheapest room type (Guest Room, 1 King Bed, $190/night) "
           "for myself with points. Confirmation number: RT01TEST01. Points redeemed: 19,000. "
           "Remaining points balance on my account page: 129,350.",
        2: "The cheapest Denver hotel with a Fitness Center is the Magnolia Hotel Denver, a "
           "Tribute Portfolio Hotel; booked its cheapest room type for Priya Nair, "
           "12/01/2026 to 12/04/2026. Confirmation number: RT02TEST01.",
        3: "The two cheapest rated-4.0+ NYC hotels were SpringHill Suites by Marriott New York "
           "Midtown Manhattan/Fifth Avenue ($410/night, $820 for two nights) and Courtyard by "
           "Marriott New York Manhattan/Times Square ($445/night). I booked SpringHill Suites by "
           "Marriott New York Midtown Manhattan/Fifth Avenue for Sam Carter. Total on the "
           "confirmation page: $820. Confirmation number: RT03TEST01.",
        4: "Cheapest Orlando hotel: Courtyard by Marriott Orlando Downtown. Cheapest room type "
           "sleeping at least four: Guest Room, 2 Double Beds ($175/night). Booked for Dana "
           "Brooks, 12/18/2026 to 12/21/2026. Total: $525. Confirmation number: RT04TEST01.",
        5: "The reservation's hotel is the Courtyard by Marriott Atlanta Downtown; its listed "
           "check-in time is 4:00 pm. Find My Reservation shows: Courtyard by Marriott Atlanta "
           "Downtown, Guest Room, 1 King Bed, check-in 11/02/2026, total $290. After canceling, "
           "the status shows Canceled.",
        6: "Reservation BRQEBMMFAQ (the earliest upcoming check-in) was canceled — the site "
           "showed 'Reservation BRQEBMMFAQ has been canceled.'. The remaining confirmed upcoming "
           "trip is at the Courtyard by Marriott Austin Downtown/Convention Center, check-in "
           "10/25/2026, total $380. My Bonvoy member tier is Platinum Elite.",
        7: "Upcoming trip: check-in 10/18/2026, room type Guest Room, 1 King Bed, total $170, at "
           "the AC Hotel Atlanta Downtown. Street address: 101 Andrew Young Intl Blvd NW, "
           "Atlanta, Georgia. Phone in the header: +1 404-524-5555. The amenity list does "
           "include a Fitness Center. Reviews page: average rating 4.1; the most recent review is "
           "titled 'Great place'. Extension booked 10/18/2026 to 10/20/2026 for Bob Chen: total "
           "$340, confirmation number RT07TEST01.",
        8: "Profile updated with phone +1 415-555-0123, street 1200 Broadway, city Oakland, "
           "state California. The exact success message shown right after saving was: 'Your "
           "profile has been updated.' After signing out and back in, the details persisted.",
        9: "Added the Visa ending 4444 (cardholder Carol Davis, expiring 09/2029) and removed "
           "the old Amex. 1 card remains: the Visa ending in 4444. Profile phone updated to "
           "+1 312-555-0188; the profile page showed 'Your profile has been updated.'.",
        10: "Removed the Austin property (Aloft by Marriott Austin Downtown) and saved The "
            "Times Square EDITION. After signing out and back in, the saved hotels list shows, "
            "in order: The Times Square EDITION, Moxy Atlanta Downtown, The Ritz-Carlton, "
            "Atlanta.",
        11: "Created the account for Fiona Gray (fiona.gray@example.com). The account page "
            "shows member tier Member and a starting points balance of 42,000. The cheapest "
            "Seattle hotel is citizenM Seattle South Lake; saved it to the list.",
        12: "7 hotels under $300 per night rated 4.0 or higher, in price order: Residence Inn "
            "by Marriott Las Vegas Hughes Center, SpringHill Suites by Marriott Las Vegas "
            "Convention Center, Residence Inn by Marriott Las Vegas Convention Center, Las Vegas "
            "Marriott, Courtyard by Marriott Las Vegas Convention Center, The ENGLiSH Hotel Las "
            "Vegas a Tribute Portfolio Hotel, Renaissance Las Vegas Hotel. Comparing the two "
            "cheapest: both cheapest room types are the Guest Room, 1 King Bed at $190 per "
            "night, 19,000 Bonvoy points per night, $380 total for the two-night stay — they "
            "are equal, so neither is cheaper (a tie).",
        13: "The two lowest points rates in Miami: citizenM Miami Brickell at 17,000 points per "
            "night (cheapest room cash rate $170 per night) and Element by Marriott Miami "
            "Brickell at 19,000 points per night (cheapest room cash rate $190 per night). On "
            "the reviews pages, citizenM Miami Brickell shows the higher average rating.",
        14: "The Boston destination page lists 12 Marriott Bonvoy hotels; the cheapest per night "
            "is the Moxy Boston Downtown. Its reviews page shows an average rating of 3.8 with "
            "1,444 reviews. Booked its cheapest room type for Alex Foley, 11/13/2026 to "
            "11/15/2026: total $720, confirmation number RT14TEST01.",
        15: "Every Chicago hotel offering both a pool and a spa: only JW Marriott Chicago. Its "
            "nightly rate is $304 and its brand is JW Marriott.",
        16: "The Westin New York Grand Central lists 5 room types in total. The largest by size "
            "is the Premium Suite, 1 King Bed, High Floor: 720 sq ft, 1 king bed + sofa bed, "
            "$1,175 per night. Booked it for Robin Stone, 11/13/2026 to 11/15/2026: total "
            "$2,350, confirmation number RT16TEST01.",
        17: "The Lexington Hotel, Autograph Collection: average rating 3.7, 4,354 reviews, 739 "
            "one-star reviews. The Westin New York Grand Central: average rating 3.9, 3,997 "
            "reviews, 509 one-star reviews. The Westin New York Grand Central has the lower share "
            "of 1-star reviews. Signed in as alice.j@test.com and saved it — the site showed "
            "'The Westin New York Grand Central has been saved to your list.'.",
        18: "Residence Inn by Marriott New York Manhattan/Times Square's top room type costs "
            "more per night — $25 more ($1,200 vs $1,175). The cheaper of the two top rooms is "
            "the Premium Suite, 1 King Bed, High Floor at The Westin New York Grand Central: "
            "1 king bed + sofa bed, 720 sq ft. Redeemed points for one night 10/30/2026 to "
            "10/31/2026 in that room: confirmation number RT18TEST01, remaining points balance "
            "157,400.",
        19: "The offer with book-by date 12/20/2026 is 'Resort Rewards: 5,000 Bonus Points "
            "Daily'; its blurb mentions 5,000 bonus points per day. The Chicago Couryard search "
            "for 12/05/2026 to 12/06/2026 returns 1 property, Courtyard by Marriott Chicago "
            "Downtown/River North, at $265 per night. The same Orlando search returns 1 Courtyard "
            "hotel.",
        20: "The longer stays category has 5 brands: Residence Inn, TownePlace Suites, Element "
            "Hotels, Marriott Vacation Club, Apartments by Marriott Bonvoy. The New York City "
            "Residence Inn search returns two properties. Residence Inn by Marriott New York "
            "Manhattan/Midtown East: check-in 4:00 pm, average rating 4.5, cheapest room Guest "
            "Room, 1 King Bed at $540 per night or 54,000 Bonvoy points per night. Residence Inn "
            "by Marriott New York Manhattan/Times Square: check-in 4:00 pm, average rating 4.0, "
            "cheapest room at $460 per night or 46,000 Bonvoy points per night. The Times Square "
            "property is cheaper per night.",
    }
    return A[index]


def wrong_answer(index: int) -> str:
    return honest_answer(index)[:40] + " — actually the answer is 999 and nothing else matches."


# ---------------------------------------------------------------- stateful mutations
def stateful_statements(index: int, db: Path, variant: str = "ok"):
    """[(sql, params)] turning a seed copy into the honest after-state (or a wrong one)."""
    if index == 0:
        if variant == "wrong_hotel":
            return [book_sql(db, "RT00WRONG9", "Hotel Adagio, Autograph Collection",
                             "Guest Room, 1 King Bed", "Jordan", "Ellis",
                             "jordan.ellis@example.com", "2026-11-06", "2026-11-08", 188, 376)]
        return [book_sql(db, "RT00TEST01", "citizenM San Francisco Union Square",
                         "Guest Room, 1 King Bed", "Jordan", "Ellis",
                         "jordan.ellis@example.com", "2026-11-06", "2026-11-08", 170, 340)]
    if index == 1:
        stmts = [("UPDATE users SET points = 129350 WHERE email = 'alice.j@test.com'", ())]
        if variant == "wrong_points":
            stmts = [("UPDATE users SET points = 130000 WHERE email = 'alice.j@test.com'", ())]
            stmts.append(book_sql(db, "RT01TEST01", "The Westin Chicago River North",
                                  "Guest Room, 1 King Bed", "Alice", "Johnson",
                                  "alice.j@test.com", "2026-10-30", "2026-10-31", 190, 19000, 19000,
                                  user_email="alice.j@test.com"))
            return stmts
        stmts.append(book_sql(db, "RT01TEST01", "The Westin Chicago River North",
                              "Guest Room, 1 King Bed", "Alice", "Johnson",
                              "alice.j@test.com", "2026-10-30", "2026-10-31", 190, 19000, 19000,
                              user_email="alice.j@test.com"))
        return stmts
    if index == 2:
        if variant == "wrong_hotel":
            return [book_sql(db, "RT02TEST01", "The Westin Denver Downtown",
                             "Guest Room, 1 King Bed", "Priya", "Nair",
                             "priya.nair@example.com", "2026-12-01", "2026-12-04", 245, 735)]
        return [book_sql(db, "RT02TEST01", "Magnolia Hotel Denver, a Tribute Portfolio Hotel",
                         "Guest Room, 1 King Bed", "Priya", "Nair",
                         "priya.nair@example.com", "2026-12-01", "2026-12-04", 190, 570)]
    if index == 3:
        if variant == "wrong_hotel":
            return [book_sql(db, "RT03TEST01", "Courtyard by Marriott New York Manhattan/Times Square",
                             "Guest Room, 1 King Bed", "Sam", "Carter",
                             "sam.carter@example.com", "2026-10-20", "2026-10-22", 445, 890)]
        return [book_sql(db, "RT03TEST01",
                         "SpringHill Suites by Marriott New York Midtown Manhattan/Fifth Avenue",
                         "Guest Room, 1 King Bed", "Sam", "Carter",
                         "sam.carter@example.com", "2026-10-20", "2026-10-22", 410, 820)]
    if index == 4:
        if variant == "wrong_room":
            return [book_sql(db, "RT04TEST01", "Courtyard by Marriott Orlando Downtown",
                             "Guest Room, 1 King Bed", "Dana", "Brooks",
                             "dana.brooks@example.com", "2026-12-18", "2026-12-21", 160, 480)]
        return [book_sql(db, "RT04TEST01", "Courtyard by Marriott Orlando Downtown",
                         "Guest Room, 2 Double Beds", "Dana", "Brooks",
                         "dana.brooks@example.com", "2026-12-18", "2026-12-21", 175, 525)]
    if index == 5:
        if variant == "wrong_target":
            return [("UPDATE reservations SET status = 'canceled' WHERE confirmation_number = 'GBNPHFBJKN'", ())]
        return [("UPDATE reservations SET status = 'canceled' WHERE confirmation_number = 'ACCEDGHDDR'", ())]
    if index == 6:
        if variant == "wrong_target":
            return [("UPDATE reservations SET status = 'canceled' WHERE confirmation_number = 'NRRQMNKHCQ'", ())]
        return [("UPDATE reservations SET status = 'canceled' WHERE confirmation_number = 'BRQEBMMFAQ'", ())]
    if index == 7:
        if variant == "wrong_total":
            return [book_sql(db, "RT07TEST01", "AC Hotel Atlanta Downtown",
                             "Guest Room, 1 King Bed", "Bob", "Chen",
                             "bob.c@test.com", "2026-10-18", "2026-10-20", 170, 999,
                             user_email="bob.c@test.com")]
        return [book_sql(db, "RT07TEST01", "AC Hotel Atlanta Downtown",
                         "Guest Room, 1 King Bed", "Bob", "Chen",
                         "bob.c@test.com", "2026-10-19", "2026-10-21", 170, 340,
                         user_email="bob.c@test.com")]
    if index == 8:
        if variant == "wrong_city":
            return [("UPDATE users SET phone = '+1 415-555-0123', street_address = '1200 Broadway', "
                     "city = 'San Francisco', state = 'California' WHERE email = 'bob.c@test.com'", ())]
        return [("UPDATE users SET phone = '+1 415-555-0123', street_address = '1200 Broadway', "
                 "city = 'Oakland', state = 'California' WHERE email = 'bob.c@test.com'", ())]
    if index == 9:
        stmts = [("DELETE FROM payment_methods WHERE user_id = (SELECT id FROM users WHERE email = 'carol.d@test.com') AND last_four = '3007'", ()),
                 ("INSERT INTO payment_methods (user_id, card_type, last_four, holder_name, exp_month, "
                  "exp_year, is_default, added_on) VALUES ((SELECT id FROM users WHERE email = "
                  "'carol.d@test.com'), 'Visa', '4444', 'Carol Davis', 9, 2029, 1, '2026-09-20')", ())]
        if variant == "wrong_card":
            stmts[1] = ("INSERT INTO payment_methods (user_id, card_type, last_four, holder_name, exp_month, "
                        "exp_year, is_default, added_on) VALUES ((SELECT id FROM users WHERE email = "
                        "'carol.d@test.com'), 'Mastercard', '4444', 'Carol Davis', 9, 2029, 1, '2026-09-20')", ())
        return stmts
    if index == 10:
        edition = hotel_id(db, "The Times Square EDITION")
        aloft = hotel_id(db, "Aloft by Marriott Austin Downtown")
        alice = db_one(db, "SELECT id FROM users WHERE email = 'alice.j@test.com'")
        if variant == "wrong_swap":
            return [(f"INSERT INTO favorites (user_id, hotel_id, saved_on) VALUES ({alice}, {edition}, '2026-09-21')", ())]
        return [(f"DELETE FROM favorites WHERE user_id = {alice} AND hotel_id = {aloft}", ()),
                (f"INSERT INTO favorites (user_id, hotel_id, saved_on) VALUES ({alice}, {edition}, '2026-09-21')", ())]
    if index == 11:
        seazs = hotel_id(db, "citizenM Seattle South Lake")
        if variant == "wrong_points":
            return [("INSERT INTO users (email, password_hash, first_name, last_name, member_number, "
                     "member_tier, points, joined_on, created_at) VALUES ('fiona.gray@example.com', "
                     "'$2b$12$fixture', 'Fiona', 'Gray', '733740761', 'Member', 1000, '2026-08-01', "
                     "'2026-09-23 09:00:00')", ()),
                    (f"INSERT INTO favorites (user_id, hotel_id, saved_on) VALUES "
                     f"((SELECT id FROM users WHERE email = 'fiona.gray@example.com'), {seazs}, '2026-09-21')", ())]
        return [("INSERT INTO users (email, password_hash, first_name, last_name, member_number, "
                 "member_tier, points, joined_on, created_at) VALUES ('fiona.gray@example.com', "
                 "'$2b$12$fixture', 'Fiona', 'Gray', '733740761', 'Member', 42000, '2026-08-01', "
                 "'2026-09-23 09:00:00')", ()),
                (f"INSERT INTO favorites (user_id, hotel_id, saved_on) VALUES "
                 f"((SELECT id FROM users WHERE email = 'fiona.gray@example.com'), {seazs}, '2026-09-21')", ())]
    if index == 14:
        if variant == "wrong_total":
            return [book_sql(db, "RT14TEST01", "Moxy Boston Downtown", "Guest Room, 1 King Bed",
                             "Alex", "Foley", "alex.foley@example.com",
                             "2026-11-13", "2026-11-15", 360, 999)]
        return [book_sql(db, "RT14TEST01", "Moxy Boston Downtown", "Guest Room, 1 King Bed",
                         "Alex", "Foley", "alex.foley@example.com",
                         "2026-11-13", "2026-11-15", 360, 720)]
    if index == 16:
        if variant == "wrong_room":
            return [book_sql(db, "RT16TEST01", "The Westin New York Grand Central",
                             "Executive Suite, 1 King Bed", "Robin", "Stone",
                             "robin.stone@example.com", "2026-11-13", "2026-11-15", 860, 1720)]
        return [book_sql(db, "RT16TEST01", "The Westin New York Grand Central",
                         "Premium Suite, 1 King Bed, High Floor", "Robin", "Stone",
                         "robin.stone@example.com", "2026-11-13", "2026-11-15", 1175, 2350)]
    if index == 17:
        westin = hotel_id(db, "The Westin New York Grand Central")
        alice = db_one(db, "SELECT id FROM users WHERE email = 'alice.j@test.com'")
        if variant == "wrong_hotel":
            lex = hotel_id(db, "The Lexington Hotel, Autograph Collection")
            return [(f"INSERT INTO favorites (user_id, hotel_id, saved_on) VALUES ({alice}, {lex}, '2026-09-21')", ())]
        return [(f"INSERT INTO favorites (user_id, hotel_id, saved_on) VALUES ({alice}, {westin}, '2026-09-21')", ())]
    if index == 18:
        stmts = [("UPDATE users SET points = 157400 WHERE email = 'david.k@test.com'", ())]
        if variant == "wrong_points":
            stmts = [("UPDATE users SET points = 200000 WHERE email = 'david.k@test.com'", ())]
        stmts.append(book_sql(db, "RT18TEST01", "The Westin New York Grand Central",
                              "Premium Suite, 1 King Bed, High Floor", "David", "Kim",
                              "david.k@test.com", "2026-10-30", "2026-10-31", 1175, 117500, 117500,
                              user_email="david.k@test.com"))
        return stmts
    raise ValueError(f"task {index} is not stateful")


# ---------------------------------------------------------------- fixture assembly
@pytest.fixture
def seed(tmp_path):
    return _acquire_seed()


def honest_run(tmp: Path, index: int, seed: Path, variant: str = "ok") -> Path:
    root = tmp / f"honest_{index:02d}_{variant}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    if index in STATEFUL:
        mutate_db(seed, root / "after.db", stateful_statements(index, root / "initial.db", variant))
    else:
        copy_db(seed, root / "after.db")
    b = RunBuilder(root, f"Marriott--{index}")
    apply_steps(b, honest_steps(index, root / "initial.db"))
    b.done(honest_answer(index))
    return root





def shortcut_run(tmp: Path, index: int, seed: Path) -> Path:
    """Correct answer (and correct DB delta) but homepage-only navigation."""
    root = tmp / f"shortcut_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    if index in STATEFUL:
        mutate_db(seed, root / "after.db", stateful_statements(index, root / "initial.db"))
    else:
        copy_db(seed, root / "after.db")
    b = RunBuilder(root, f"Marriott--{index}")
    b.step("/", "goto", {})
    b.done(honest_answer(index))
    return root


def wrong_answer_run(tmp: Path, index: int, seed: Path) -> Path:
    root = tmp / f"wrong_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    if index in STATEFUL:
        mutate_db(seed, root / "after.db", stateful_statements(index, root / "initial.db"))
    else:
        copy_db(seed, root / "after.db")
    b = RunBuilder(root, f"Marriott--{index}")
    apply_steps(b, honest_steps(index, root / "initial.db"))
    b.done(wrong_answer(index))
    return root


def state_mismatch_run(tmp: Path, index: int, seed: Path) -> Path:
    """Honest navigation + honest answer but NO DB delta (self-report only)."""
    root = tmp / f"nomatch_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, f"Marriott--{index}")
    apply_steps(b, honest_steps(index, root / "initial.db"))
    b.done(honest_answer(index))
    return root


def mutated_readonly_run(tmp: Path, index: int, seed: Path) -> Path:
    """Read-only honest run but with an unrelated row mutated in the after-DB."""
    root = tmp / f"mutro_{index:02d}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    mutate_db(seed, root / "after.db",
              [("UPDATE users SET points = points + 1 WHERE email = 'alice.j@test.com'", ())])
    b = RunBuilder(root, f"Marriott--{index}")
    apply_steps(b, honest_steps(index, root / "initial.db"))
    b.done(honest_answer(index))
    return root


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("index", range(21))
def test_honest_pass(tmp_path, seed, index):
    run = honest_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is True, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", range(21))
def test_noop_fail(tmp_path, seed, index):
    run = noop_run(tmp_path, index)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", range(21))
def test_wrong_answer_fail(tmp_path, seed, index):
    run = wrong_answer_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", range(21))
def test_shortcut_fail(tmp_path, seed, index):
    run = shortcut_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_state_mismatch_fail(tmp_path, seed, index):
    run = state_mismatch_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


WRONG_DELTA_VARIANTS = {0: "wrong_hotel", 1: "wrong_points", 2: "wrong_hotel", 3: "wrong_hotel",
                        4: "wrong_room", 5: "wrong_target", 6: "wrong_target", 7: "wrong_total",
                        8: "wrong_city", 9: "wrong_card", 10: "wrong_swap", 11: "wrong_points",
                        14: "wrong_total", 16: "wrong_room", 17: "wrong_hotel", 18: "wrong_points"}


@pytest.mark.parametrize("index", sorted(STATEFUL))
def test_wrong_delta_fail(tmp_path, seed, index):
    run = honest_run(tmp_path, index, seed, variant=WRONG_DELTA_VARIANTS[index])
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


@pytest.mark.parametrize("index", READ_ONLY)
def test_mutated_after_fail(tmp_path, seed, index):
    run = mutated_readonly_run(tmp_path, index, seed)
    result = run_verifier(index, run)
    assert result["pass"] is False, json.dumps(result, indent=1)


# ---------------------------------------------------------------- package tampering
def test_task_id_mismatch_fail(tmp_path, seed):
    root = tmp_path / "tamper_taskid"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, "Marriott--19")
    apply_steps(b, honest_steps(0, root / "initial.db"))
    b.done(honest_answer(0))
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_offsite_url_fail(tmp_path, seed):
    root = tmp_path / "tamper_offsite"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, "Marriott--0")
    apply_steps(b, honest_steps(0, root / "initial.db"))
    b.step("/", "goto", {}, url="https://evil.example.com/steal")
    b.done(honest_answer(0))
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_missing_screenshot_fail(tmp_path, seed):
    root = tmp_path / "tamper_shot"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, "Marriott--0")
    apply_steps(b, honest_steps(0, root / "initial.db"))
    b.done(honest_answer(0))
    shots = sorted((root / "screenshots").glob("step_*.png"))
    shots[1].unlink()
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_nondone_trajectory_fail(tmp_path, seed):
    root = tmp_path / "tamper_nondone"
    root.mkdir(parents=True)
    copy_db(seed, root / "initial.db")
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, "Marriott--0")
    apply_steps(b, honest_steps(0, root / "initial.db"))
    b.done(honest_answer(0), terminated=False, reason="max_steps")
    result = run_verifier(0, root)
    assert result["pass"] is False


def test_tampered_seed_fails_closed(tmp_path, seed):
    root = tmp_path / "tamper_seed"
    root.mkdir(parents=True)
    mutate_db(seed, root / "initial.db",
              [("UPDATE hotels SET base_rate = base_rate + 1 WHERE marsha = 'SFOFU'", ())])
    copy_db(seed, root / "after.db")
    b = RunBuilder(root, "Marriott--0")
    apply_steps(b, honest_steps(0, root / "initial.db"))
    b.done(honest_answer(0))
    result = run_verifier(0, root)
    assert result["pass"] is False and result.get("infra_error") is True


def test_unavailable_db_fails_closed(tmp_path, seed):
    root = tmp_path / "tamper_nodb"
    root.mkdir(parents=True)
    b = RunBuilder(root, "Marriott--0")
    apply_steps(b, honest_steps(0, seed))
    b.done(honest_answer(0))
    import subprocess, sys as _sys
    verifier = Path(__file__).resolve().parents[1] / "verify_0.py"
    r = subprocess.run([_sys.executable, str(verifier), "--run_dir", str(root),
                        "--initial_db", "/nonexistent/x.db"], capture_output=True, text=True)
    result = json.loads(r.stdout)
    assert result["pass"] is False and result.get("infra_error") is True


_original_honest_answer = honest_answer

def honest_answer(index):
    answer = _original_honest_answer(index)
    replacements = {
        7: "AC Hotel Atlanta Downtown booked for 10/19/2026 to 10/21/2026. Total $340, confirmation RT07TEST01.",
        8: "Your profile contact details have been updated.",
        9: "Amex removed. One card remains: Visa ending 4444, expiring 09/2029.",
        15: "JW Marriott Chicago, brand JW Marriott. Guest Room, 2 Double Beds sleeps 4 at $335 per night, $670 total.",
        19: "Chicago has 1 Courtyard: Courtyard by Marriott Chicago Downtown/River North at $265 per night. Orlando has 1 Courtyard: Courtyard by Marriott Orlando Downtown at $160 per night. Orlando is cheaper.",
    }
    return replacements.get(index, answer)

_original_honest_steps = honest_steps

def honest_steps(index, db):
    steps = _original_honest_steps(index, db)
    if index == 15:
        steps.append((hotel_path("CHIJW", "rooms"), "goto", {}))
    return steps
