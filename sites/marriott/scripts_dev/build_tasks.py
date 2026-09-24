"""Generate sites/marriott/tasks.jsonl anchored to the frozen seed catalog.

Writes the contributor-row shape ONLY (web_name, id, ques, web,
upstream_url) — no verifier_path / judge_rubric / answer keys.

Every task is a goal-style brief whose honest walkthrough runs a deep
functional chain (search -> filter -> compare -> detail -> book -> confirm,
or the account/reservation/loyalty equivalents), 15+ real browser steps,
never a single-step information lookup, and never a step-by-step
instruction list. Answers are anchored on page-specific facts an agent must
read off the rendered pages (exact rates, points values, review counts,
confirmation numbers, amenity lists) so the tasks cannot be answered from
an LLM's prior knowledge.

Run AFTER the final seed build:  python3 scripts_dev/build_tasks.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Anchor tasks on the SHIPPED seed, never the mutable runtime instance —
# walkthrough bookings mutate instance/marriott.db and would silently
# re-anchor the reservation lookups.
os.environ.setdefault("WEBHARBOR_MIRROR_DB",
                      str(ROOT / "instance_seed" / "marriott.db"))

WEB = "http://localhost:40086/"
UPSTREAM = "https://www.marriott.com/"

tasks = []


def add(ques: str) -> None:
    assert len(ques.split()) <= 100, f"task {len(tasks)} exceeds 100 words"
    tasks.append({
        "web_name": "Marriott",
        "id": f"Marriott--{len(tasks)}",
        "ques": " ".join(ques.split()),
        "web": WEB,
        "upstream_url": UPSTREAM,
    })


def fmt(d) -> str:
    return d.strftime("%m/%d/%Y")


def main() -> None:
    import app as m
    with m.app.app_context():
        from app import (Brand, Destination, Hotel, Offer, Reservation,
                         Review, RoomType, User)
        from datetime import date

        def dest(slug):
            d = Destination.query.filter_by(slug=slug).first()
            assert d is not None, f"destination {slug} missing"
            return d

        def hotels_in(slug, order=Hotel.marsha):
            d = dest(slug)
            return (Hotel.query.filter_by(destination_id=d.id)
                    .order_by(order).all())

        def cheapest_room(hotel):
            return sorted(hotel.room_types, key=lambda r: r.base_rate)[0]

        def largest_room(hotel):
            return sorted(hotel.room_types,
                          key=lambda r: -(r.size_sqft or 0))[0]

        def priciest_room(hotel):
            return sorted(hotel.room_types, key=lambda r: -r.base_rate)[0]

        # ============================================================
        # A. BOOKING CHAINS (search -> filter -> compare -> book)
        # ============================================================
        # 1 -- rated-then-cheapest booking in San Francisco
        sf = [h for h in hotels_in("san-francisco", Hotel.base_rate)
              if (h.rating_avg or 0) >= 4.0]
        assert sf, "no 4.0+ San Francisco hotels"
        add(f"You're planning a two-night escape to San Francisco: check in "
            f"11/06/2026, check out 11/08/2026, two adults, one room. Among "
            f"hotels rated 4.0 or higher, reserve the most affordable one in "
            f"its cheapest available room type for guest Jordan Ellis "
            f"(jordan.ellis@example.com), paying with card 4012888888881881 "
            f"expiring 11/2029. Report the confirmation number and the total "
            f"shown on the confirmation page.")

        # 2 -- points redemption booking (requires Bonvoy sign-in)
        chi = sorted(hotels_in("chicago", Hotel.points_rate),
                     key=lambda h: h.points_rate)
        assert chi and chi[0].points_rate, "Chicago points rates missing"
        add(f"Sign in as alice.j@test.com (password TestPass123!). Using a "
            f"points-rate search for Chicago with check-in 10/30/2026 and "
            f"check-out 10/31/2026, one room and one adult, redeem Bonvoy "
            f"points for the stay with the lowest nightly points rate, "
            f"booking its cheapest room type for yourself. Report the "
            f"confirmation number, the points redeemed, and your remaining "
            f"points balance shown on your account page.")

        # 3 -- amenity-constrained booking in Denver
        den = [h for h in hotels_in("denver", Hotel.base_rate)
               if "Fitness Center" in h.amenity_list]
        assert den, "no Denver hotel lists a Fitness Center"
        add(f"Your employer sends you to Denver for three nights, "
            f"12/01/2026 to 12/04/2026, one room, one adult. Book the "
            f"cheapest Denver hotel whose amenity listing includes a Fitness "
            f"Center, in its cheapest room type, for guest Priya Nair "
            f"(priya.nair@example.com) with Visa card 4500123456789012 "
            f"expiring 08/2028. Report the hotel's name and the confirmation "
            f"number on the confirmation page.")

        # 4 -- compare the two cheapest rated NYC hotels, then book
        ny = [h for h in hotels_in("new-york-city", Hotel.base_rate)
              if (h.rating_avg or 0) >= 4.0]
        assert len(ny) >= 2, "not enough 4.0+ NYC hotels"
        add(f"Two colleagues will share one room in New York City for "
            f"10/20/2026 to 10/22/2026. Compare the two cheapest hotels "
            f"rated 4.0 or higher by opening their rooms pages and noting "
            f"each one's cheapest room type rate. Reserve the option with "
            f"the lower two-night total for guest Sam Carter "
            f"(sam.carter@example.com) with card 5555666677778888 expiring "
            f"03/2029. Report which hotel you booked and the total shown on "
            f"the confirmation page.")

        # 5 -- family occupancy-constrained booking in Orlando
        orl = hotels_in("orlando", Hotel.base_rate)
        assert orl, "no Orlando hotels"
        add(f"Your family of four needs one room in Orlando for "
            f"12/18/2026 to 12/21/2026. At the cheapest Orlando hotel by "
            f"nightly rate, book its cheapest room type that sleeps at "
            f"least four guests, for guest Dana Brooks "
            f"(dana.brooks@example.com) with Mastercard 5200828282828220 "
            f"expiring 10/2027. Report the room type name, the total, and "
            f"the confirmation number shown on the confirmation page.")

        # ============================================================
        # B. RESERVATION MANAGEMENT
        # ============================================================
        # 6 -- lookup by confirmation number, cancel, re-verify
        alice = User.query.filter_by(email="alice.j@test.com").first()
        assert alice is not None
        alice_conf = (Reservation.query
                      .filter(Reservation.user_id == alice.id,
                              Reservation.status == "confirmed",
                              Reservation.checkin >= date(2026, 9, 23))
                      .order_by(Reservation.checkin).first())
        assert alice_conf is not None, "alice has no upcoming reservation"
        add(f"Sign in as alice.j@test.com (password TestPass123!). A "
            f"confirmation email lists reservation number "
            f"{alice_conf.confirmation_number} under guest Alice Johnson. "
            f"From your trips page, open that reservation's hotel page and "
            f"report its listed check-in time. Then look the reservation up "
            f"on Find My Reservation: report the hotel, room type, "
            f"check-in date, and total. Finally cancel it and look it up "
            f"again to report the status shown.")

        # 7 -- disambiguation among several upcoming trips
        david = User.query.filter_by(email="david.k@test.com").first()
        assert david is not None
        upcoming = (Reservation.query
                   .filter(Reservation.user_id == david.id,
                           Reservation.status == "confirmed",
                           Reservation.checkin >= date(2026, 9, 23))
                   .order_by(Reservation.checkin).all())
        assert len(upcoming) >= 2, "david needs 2+ upcoming trips"
        add(f"Sign in as david.k@test.com (password TestPass123!). You have "
            f"more than one upcoming trip. Cancel the upcoming reservation "
            f"with the earliest check-in date, then look it up again on Find "
            f"My Reservation to confirm it shows as canceled. Report the "
            f"cancellation message. Then look up your remaining confirmed "
            f"upcoming trip on Find My Reservation as well and report its "
            f"hotel, check-in date, and total, plus your Bonvoy member tier.")

        # 8 -- trip -> hotel facts -> reviews chain (bob)
        bob = User.query.filter_by(email="bob.c@test.com").first()
        assert bob is not None
        bob_conf = (Reservation.query
                    .filter(Reservation.user_id == bob.id,
                            Reservation.status == "confirmed",
                            Reservation.checkin >= date(2026, 9, 23))
                    .order_by(Reservation.checkin).first())
        assert bob_conf is not None, "bob has no upcoming trip"
        bob_hotel = bob_conf.hotel
        facts = []
        if bob_hotel.address_line:
            facts.append("its exact street address and the phone number in "
                        "the header")
        else:
            facts.append("its listed check-in and check-out times")
        add(f"Sign in as bob.c@test.com (password TestPass123!). Open your "
            f"upcoming trip's hotel and report the trip's check-in date, "
            f"room type, and total. From the hotel page report "
            f"{' '.join(facts)}, and whether its amenity list includes a "
            f"fitness center. Visit that hotel's reviews page and report "
            f"the average rating and the title of the most recent review "
            f"shown. Then extend your stay: book that hotel's cheapest room "
            f"type for 10/18/2026 to 10/20/2026 under guest Bob Chen with "
            f"card 5242882882828282 expiring 04/2029, and report the "
            f"confirmation number and total.")

        # ============================================================
        # C. ACCOUNT DOMAIN
        # ============================================================
        # 9 -- profile update, verified by sign-out / sign-in
        add(f"Sign in as bob.c@test.com (password TestPass123!). Your office "
            f"moved: update your profile with phone +1 415-555-0123, street "
            f"1200 Broadway, city Oakland, state California. Then sign out "
            f"and sign back in to confirm the details persisted, and report "
            f"the exact success message the site showed right after saving.")

        # 10 -- payment methods: add then remove, plus profile update
        add(f"Sign in as carol.d@test.com (password TestPass123!). Add a "
            f"Visa card, number 4242424242424444, cardholder Carol Davis, "
            f"expiring 09/2029. Then remove your old Amex card and report "
            f"how many cards remain and the last four digits of each. Also "
            f"update your profile phone number to +1 312-555-0188 and report "
            f"the success message the profile page shows.")

        # 11 -- saved hotels: remove one city, add another hotel, verify
        add(f"Sign in as alice.j@test.com (password TestPass123!). From "
            f"your saved hotels, remove the property located in Austin. "
            f"Then search New York City hotels and save The Times Square "
            f"EDITION to your list. Sign out and sign back in, then report "
            f"the final names in your saved hotels, in the order shown.")

        # 12 -- register a fresh account and use it
        sea = hotels_in("seattle", Hotel.base_rate)
        assert sea, "no Seattle hotels"
        add(f"Create a new Marriott Bonvoy account for Fiona Gray with "
            f"email fiona.gray@example.com (choose your own password of at "
            f"least 8 characters). Once signed in, report the member tier "
            f"and starting points balance the account page shows. Then "
            f"search Seattle hotels, open the cheapest one, and save it to "
            f"your list; report its exact name.")

        # ============================================================
        # D. SEARCH & DISCOVERY
        # ============================================================
        # 13 -- budget + rating filter chain with a tie-break and runner-up
        vegas = [h for h in hotels_in("las-vegas", Hotel.base_rate)
                 if h.base_rate < 300 and (h.rating_avg or 0) >= 4.0]
        assert len(vegas) >= 3, "Vegas budget set too thin"
        add(f"For a budget group trip to Las Vegas, 11/13/2026 to "
            f"11/15/2026, find every hotel under $300 per night rated 4.0 "
            f"or higher. Report how many match and their names in price "
            f"order. Then compare the two cheapest matches: open both "
            f"hotels' rooms pages and report the nightly rate and Bonvoy "
            f"points rate of each one's cheapest room type and its total "
            f"for the two-night stay, and which of the two works out "
            f"cheaper.")

        # 14 -- points-value comparison across the two lowest-points hotels
        mia = sorted(hotels_in("miami", Hotel.points_rate),
                     key=lambda h: h.points_rate)
        assert mia and mia[0].points_rate, "Miami points rates missing"
        add(f"You have a pile of Bonvoy points and a free night in Miami on "
            f"11/20/2026 to 11/21/2026. Using the points-rate search for "
            f"Miami, identify the two properties with the lowest nightly "
            f"points rates. Open both hotels' rooms pages and report each "
            f"one's exact points rate and the nightly cash rate of its "
            f"cheapest room type. Also report which of the two shows the "
            f"higher average rating on its reviews page.")

        # 15 -- destination page -> cheapest -> reviews -> booking chain
        bos = hotels_in("boston", Hotel.base_rate)
        assert bos, "no Boston hotels"
        add(f"Plan a Boston getaway for 11/13/2026 to 11/15/2026, two "
            f"guests, one room. From the Boston destination page, identify "
            f"how many Marriott Bonvoy hotels it lists and pick the "
            f"cheapest per night. Check that hotel's reviews page and "
            f"report its average rating and total review count. Then book "
            f"its cheapest room type for guest Alex Foley "
            f"(alex.foley@example.com) with Amex 378282246310005 expiring "
            f"06/2028, and report the total and confirmation number.")

        # 16 -- amenity hunt across candidate hotels
        chi_all = hotels_in("chicago")
        both = [h for h in chi_all
                if any("Pool" in a for a in h.amenity_list)
                and "Spa" in h.amenity_list]
        assert both, "no Chicago hotel has pool + spa"
        add(f"You want a Chicago hotel with both a pool and a spa for a "
            f"recovery weekend, 11/06/2026 to 11/08/2026. Search Chicago "
            f"hotels and check the amenity sections of the candidate "
            f"properties. Report every hotel that offers both, plus each "
            f"one's nightly rate and brand.")

        # ============================================================
        # E. ROOMS & REVIEWS DEEP DIVES
        # ============================================================
        # 17 -- rooms deep dive + booking the largest room
        westin = Hotel.query.filter_by(marsha="NYCZW").first()
        assert westin is not None, "Westin NYC missing"
        add(f"Open the rooms page of {westin.name}. Report the name, square "
            f"footage, bed setup, and nightly rate of its largest room type "
            f"by size, and how many room types the hotel lists in total. "
            f"Then, for a stay of 11/13/2026 to 11/15/2026, book that "
            f"largest room type for guest Robin Stone "
            f"(robin.stone@example.com) with Visa 4000056655665556 expiring "
            f"02/2029, and report the total and the confirmation number.")

        # 18 -- reviews sentiment comparison + save the winner
        lex = Hotel.query.filter(
            Hotel.name == "The Lexington Hotel, Autograph Collection").first()
        assert lex is not None and westin is not None
        add(f"Planning a work trip to New York City for 10/30/2026 to "
            f"11/01/2026, you're torn between {lex.name} and {westin.name}. "
            f"Visit both hotels' reviews pages and report each hotel's "
            f"average rating, total review count, and 1-star review count. "
            f"Then report which hotel has the lower share of 1-star reviews. "
            f"Sign in as alice.j@test.com (password TestPass123!) and save "
            f"that hotel to your saved list; report the confirmation "
            f"message shown.")

        # 19 -- priciest room comparison between the two hotels
        ri_ts = Hotel.query.filter(
            Hotel.name == "Residence Inn by Marriott New York "
            "Manhattan/Times Square").first()
        assert ri_ts is not None
        add(f"Sign in as david.k@test.com (password TestPass123!). Compare "
            f"the most expensive room types at {westin.name} and "
            f"{ri_ts.name}: visit both hotels' rooms pages and report which "
            f"hotel's top room type costs more per night and by how many "
            f"dollars, plus the bed setup and square footage of the cheaper "
            f"of the two top rooms. Then redeem points for one night, "
            f"10/30/2026 to 10/31/2026, in that cheaper top room and report "
            f"the confirmation number and your remaining points balance.")

        # ============================================================
        # F. OFFERS & BRANDS
        # ============================================================
        # 20 -- offers page -> brand-filtered search across two cities
        target_offer = Offer.query.filter_by(book_by="12/20/2026").first()
        assert target_offer is not None, "12/20/2026 offer missing"
        cy_chi = [h for h in chi_all
                  if h.brand.code == "CY"]
        assert cy_chi, "no Chicago Courtyard"
        add(f"Open the Special Offers page and report the title of the "
            f"offer whose book-by date is 12/20/2026 and the bonus points "
            f"amount its blurb mentions. Then search Chicago hotels for "
            f"12/05/2026 to 12/06/2026 filtered to the Courtyard brand: "
            f"report how many properties appear and the nightly rate of the "
            f"cheapest one. Repeat the same brand-filtered search for "
            f"Orlando the same dates and report how many Courtyard hotels "
            f"appear there.")

        # 21 -- brands taxonomy -> brand-filtered search with rooms compare
        ri_ny = [h for h in hotels_in("new-york-city")
                 if h.brand.code == "RZ2"]
        assert len(ri_ny) >= 2, "need 2+ NYC Residence Inns"
        add(f"On the Our Brands page, report how many brands belong to the "
            f"longer stays category and list their names. Then search New "
            f"York City hotels for 12/05/2026 to 12/07/2026 filtered to the "
            f"Residence Inn brand: visit each property's page to report "
            f"its listed check-in time and its average rating, and its "
            f"rooms page for the nightly rate and Bonvoy points rate of "
            f"its cheapest room type. Report which of them is cheaper per "
            f"night.")

    out = "\n".join(json.dumps(t, ensure_ascii=False) for t in tasks) + "\n"
    (ROOT / "tasks.jsonl").write_text(out)
    print(f"wrote {len(tasks)} tasks to tasks.jsonl")


if __name__ == "__main__":
    main()
