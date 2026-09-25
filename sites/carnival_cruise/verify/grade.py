"""Shared deterministic CARNIVAL CRUISE task grading.

grade(number) is invoked by verify_<number>.py with the agent run directory.
Ground truth is HARDCODED in answers.py (never in tasks.jsonl). Checks per task:
  1. harness gates (completed run, local origin, real screenshots)  [verify_lib]
  2. navigation evidence for the pages the task depends on
  3. answer checks against frozen ground truth (numbers / money / tokens /
     times / day-numbers, negation-aware, with bounded word forms)
  4. DB after-state: read-only tasks leave every table unchanged; the two
     stateful tasks (13: register+book, 17: add excursion) must produce
     exactly the requested rows/fields and preserve the rest
"""
import re
import sys

from verify_lib import (
    Judge, load_run, parse_args, resolve_db, rows, one, scalar, preserved,
    new_rows, tables_unchanged, navigated_path, navigated_prefix,
    navigated_query, contains_count, contains_money, affirm_number,
    affirm_money, affirm_score, affirm_time, day_number, affirms,
    affirms_any, contains_any, contains_number, norm, final_answer,
    step_text, shot_at,
)
import answers as A

STATEFUL = {13, 17}

# URL substring each task's evidence screenshot must be bound to (the page the
# task depends on; anti "answer without opening the page" shortcut).
SHOT_ANCHORS = {
    0: "/cruise-search", 1: "/cruise-search", 2: "/cruise-search",
    3: "/cruise-search", 4: "/cruise-search", 5: "/cruise-search",
    6: None, 7: "3-days/baw", 8: "5-day-bermuda-cruise",
    9: "4-day-baja-mexico-cruise", 10: "3-days/baw", 11: "/cruise-search",
    12: "long-beach-los-angeles/firenze", 13: "/booking",
    14: "9N382701", 15: "/booked/manage", 16: "9N510304", 17: "9N382702",
    18: "/shore-excursions/cozumel", 19: "/shore-excursions/cozumel",
    20: "celebration-key", 21: "/shore-excursions/juneau", 22: "amber-cove",
    23: "carnival-celebration", 24: "mardi-gras", 25: "carnival-jubilee",
    26: "carnival-celebration", 27: "/drink-packages", 28: "contact-us",
    29: "/favorites",
}


def _tz_ok(fa):
    return re.search(r"\b(e\.?t\.?|eastern(?:\s+time)?)\b", norm(fa)) is not None


def _booking_row(data, number_attr, booking_number):
    return scalar(data, "bookings", booking_number=booking_number)


def grade(number, emit=True):
    args = parse_args()
    j = Judge(f"Carnival Cruise--{number}")
    t = load_run(args.run_dir)
    fa = final_answer(t)
    init_db = args.initial_db or resolve_db(None, args.container, "instance_seed")
    after_db = args.after_db or resolve_db(None, args.container, "instance")
    b, a = rows(init_db), rows(after_db)
    j.bind_run(t, require_answer=True, shot_url=SHOT_ANCHORS.get(number))

    if number not in STATEFUL:
        if b is None or a is None:
            j.check("db_available", False, "initial/after DB unavailable (fail-closed)")
        else:
            changed = tables_unchanged(init_db, after_db)
            j.check("db_unchanged", changed == [],
                    f"changed tables: {changed}" if changed else "all tables unchanged")

    # ---------------- read-only catalog tasks ----------------
    if number == 0:
        j.check("search_visited_mia", navigated_query(t, "/cruise-search", port="MIA"),
                "cruise search filtered to Miami departures")
        j.check("answer_title", affirms(fa, A.T0_TITLE), fa)
        j.check("answer_price", affirm_money(fa, A.T0_PRICE), fa)

    elif number == 1:
        j.check("search_visited_gal", navigated_query(t, "/cruise-search", port="GAL"),
                "cruise search filtered to Galveston departures")
        j.check("answer_count", contains_count(fa, A.T1_COUNT), fa)

    elif number == 2:
        j.check("search_visited_alaska", navigated_query(t, "/cruise-search", dest="A"),
                "cruise search filtered to Alaska")
        shot_ok, shot_note = shot_at(t, "/cruise-search")
        j.check("shot_search_page", shot_ok, shot_note)
        j.check("answer_count", contains_count(fa, A.T2_COUNT), fa)
        j.check("answer_shortest_days", contains_count(fa, A.T2_MIN_DAYS)
                and affirms_any(fa, ["day", "days", "duration"]), fa)

    elif number == 3:
        j.check("search_visited_mia", navigated_query(t, "/cruise-search", port="MIA"),
                "cruise search filtered to Miami departures")
        j.check("answer_title", affirms(fa, A.T3_TITLE), fa)
        j.check("answer_ship", affirms(fa, A.T3_SHIP), fa)
        j.check("answer_price", affirm_money(fa, A.T3_PRICE), fa)

    elif number == 4:
        j.check("search_visited_msy", navigated_query(t, "/cruise-search", port="MSY"),
                "cruise search filtered to New Orleans departures")
        j.check("answer_title", affirms(fa, A.T4_TITLE), fa)
        j.check("answer_days", contains_count(fa, A.T4_DAYS), fa)
        j.check("answer_price", affirm_money(fa, A.T4_PRICE), fa)

    elif number == 5:
        j.check("search_visited_sorted", navigated_query(t, "/cruise-search", port="MIA", sort="-fromprice"),
                "Miami departures sorted by price high-to-low")
        j.check("answer_title", affirms(fa, A.T5_TITLE), fa)
        j.check("answer_price", affirm_money(fa, A.T5_PRICE), fa)

    elif number == 6:
        opened = (navigated_prefix(t, "/cruise-ships/")
                  or navigated_query(t, "/search", q={"bolt", "BOLT", "Bolt"}))
        j.check("ships_or_search_visited", opened,
                "a ship page or a site search for BOLT was opened")
        s1_ok, s1_note = shot_at(t, "/cruise-ships/")
        s2_ok, s2_note = shot_at(t, "/search")
        j.check("shot_ships_or_search_page", s1_ok or s2_ok,
                s1_note if s1_ok else s2_note)
        missing = [s for s in A.T6_SHIPS if not affirms(fa, s)]
        j.check("answer_all_bolt_ships", not missing,
                f"missing ships: {missing}" if missing else f"all of {A.T6_SHIPS}")

    elif number == 7:
        j.check("baw_itinerary_visited", navigated_path(t, A.BAW_URL),
                "3-Day The Bahamas from Miami (Conquest) itinerary page")
        j.check("answer_port", affirms(fa, A.T7_PORT), fa)
        j.check("answer_day", day_number(fa, A.T7_DAY), fa)
        j.check("answer_depart_time", affirm_time(fa, *A.T7_DEPART), fa)

    elif number == 8:
        j.check("bermuda_itinerary_visited", navigated_prefix(t, A.BERMUDA5_PREFIX),
                "5-Day Bermuda from Manhattan itinerary page")
        j.check("answer_bermuda_days",
                day_number(fa, A.T8_DAYS[0]) and day_number(fa, A.T8_DAYS[1]),
                f"Bermuda port call spans days {A.T8_DAYS}")
        j.check("answer_port_duration", contains_count(fa, 24) and affirms(fa, "hours"),
                "24 hours between day 3 arrival and day 4 departure")
        j.check("answer_port_time", affirm_time(fa, 4, 0, "PM"), "4 PM arrival and departure")

    elif number == 9:
        j.check("baja_itinerary_visited", navigated_prefix(t, A.BAJA4_PREFIX),
                "4-Day Baja Mexico from Long Beach itinerary page")
        j.check("answer_port", affirms(fa, A.T9_PORT), fa)
        j.check("answer_day", day_number(fa, A.T9_DAYS[0]) or day_number(fa, A.T9_DAYS[1]),
                f"day {A.T9_DAYS[0]} (day {A.T9_DAYS[1]} on the LXP variant)")

    elif number == 10:
        j.check("baw_itinerary_visited", navigated_path(t, A.BAW_URL),
                "3-Day The Bahamas from Miami (Conquest) itinerary page")
        j.check("answer_burger_venue", affirms_any(fa, [A.T10_VENUE, "Guys Burger Joint",
                                                        "Guy's Burger Joint"]),
                fa)

    elif number == 11:
        j.check("search_visited_gal", navigated_query(t, "/cruise-search", port="GAL"),
                "cruise search filtered to Galveston departures")
        j.check("answer_title", affirms(fa, A.T11_TITLE), fa)
        j.check("answer_ship", affirms(fa, A.T11_SHIP), fa)
        j.check("answer_price", affirm_money(fa, A.T11_PRICE), fa)

    elif number == 12:
        j.check("firenze_baja_visited", navigated_prefix(t, A.BAJA4_FRENZE_PREFIX),
                "4-Day Baja Mexico from Long Beach aboard Carnival Firenze")
        j.check("answer_arrival_time", affirm_time(fa, *A.T12_ARRIVE), fa)

    # ---------------- stateful tasks ----------------
    elif number == 13:
        _booking_task(j, t, a, b, fa)

    elif number == 14:
        j.check("booking_detail_visited",
                navigated_path(t, f"/booked/manage/{A.T14_BOOKING}") or navigated_path(t, "/account"),
                f"booking {A.T14_BOOKING} detail (or account page) as alice")
        j.check("answer_cabin", contains_any(fa, [A.T14_CABIN, A.T14_CABIN.lower(),
                                                  A.T14_CABIN.replace("C", "c")]), fa)
        j.check("answer_category", affirms(fa, A.T14_CATEGORY), fa)

    elif number == 15:
        j.check("manage_visited",
                navigated_prefix(t, "/booked/manage") or navigated_path(t, "/account"),
                "manage bookings (or account) as alice")
        j.check("answer_booking", contains_any(fa, [A.T15_BOOKING, A.T15_BOOKING.lower()]), fa)
        j.check("answer_title", affirms(fa, A.T15_TITLE), fa)
        j.check("no_cancellation_performed",
                a is not None and all(r["status"] == "confirmed"
                                      for r in a["bookings"] if r["booking_number"] == A.T15_BOOKING),
                "booking 9N382701 still confirmed in the after-state DB")

    elif number == 16:
        j.check("booking_detail_visited", navigated_path(t, f"/booked/manage/{A.T16_BOOKING}"),
                f"booking {A.T16_BOOKING} detail as bob")
        j.check("answer_excursion", affirms(fa, A.T16_EXCURSION), fa)
        j.check("answer_guests", contains_count(fa, A.T16_GUESTS), fa)
        j.check("answer_price", affirm_money(fa, A.T16_PRICE), fa)

    elif number == 17:
        _excursion_task(j, t, a, b, fa)

    elif number == 18:
        j.check("cozumel_sorted_visited",
                navigated_query(t, "/shore-excursions/cozumel", sort="price"),
                "Cozumel excursions sorted by price low-to-high")
        j.check("answer_title", affirms(fa, A.T18_TITLE), fa)
        j.check("answer_price", affirm_money(fa, A.T18_PRICE), fa)

    elif number == 19:
        j.check("cozumel_visited", navigated_path(t, "/shore-excursions/cozumel"),
                "Cozumel shore excursions page")
        j.check("answer_title", affirms(fa, A.T19_TITLE), fa)
        j.check("answer_price", affirm_money(fa, A.T19_PRICE), fa)

    elif number == 20:
        j.check("pearl_cove_visited", navigated_prefix(t, "/shore-excursions/celebration-key"),
                "Pearl Cove Beach Club page at Celebration Key")
        j.check("answer_price", affirm_money(fa, A.T20_PRICE), fa)
        j.check("answer_duration", contains_count(fa, int(A.T20_HOURS))
                and affirms_any(fa, ["hour", "hours"]), fa)

    elif number == 21:
        j.check("juneau_visited", navigated_path(t, "/shore-excursions/juneau"),
                "Juneau shore excursions page")
        j.check("answer_title", affirms(fa, A.T21_TITLE), fa)
        j.check("answer_rating", affirm_score(fa, A.T21_RATING), fa)
        j.check("answer_reviews", contains_count(fa, A.T21_REVIEWS)
                and affirms_any(fa, ["review", "reviews", "rating"]), fa)

    elif number == 22:
        j.check("amber_cove_visited", navigated_prefix(t, "/shore-excursions/amber-cove"),
                "Amber Cove shore excursions")
        j.check("answer_age_context", affirms_any(fa, ["minimum age", "min age", "age requirement",
                                                       "minimum age is", "years old"]), fa)
        j.check("answer_min_age", contains_count(fa, A.T22_MIN_AGE), fa)

    elif number == 23:
        j.check("celebration_visited", navigated_path(t, "/cruise-ships/carnival-celebration"),
                "Carnival Celebration ship page")
        j.check("answer_zone_count", contains_count(fa, A.T23_COUNT), fa)
        missing = [z for z in A.T23_ZONES if not affirms(fa, z)]
        j.check("answer_all_zones", not missing,
                f"missing zones: {missing}" if missing else f"all {A.T23_COUNT} zones")

    elif number == 24:
        j.check("mardi_gras_visited", navigated_path(t, "/cruise-ships/mardi-gras"),
                "Mardi Gras ship page")
        missing = [v for v in A.T24_VENUES if not affirms(fa, v)]
        j.check("answer_all_included_dining", not missing,
                f"missing venues: {missing}" if missing else f"all of {A.T24_VENUES}")

    elif number == 25:
        j.check("jubilee_visited", navigated_path(t, "/cruise-ships/carnival-jubilee"),
                "Carnival Jubilee ship page")
        j.check("answer_home_port", affirms(fa, A.T25_PORT), fa)

    elif number == 26:
        j.check("celebration_visited", navigated_path(t, "/cruise-ships/carnival-celebration"),
                "Carnival Celebration ship page")
        found = [x for x in A.T26_ADDITIONAL if affirms(fa, x)]
        j.check("answer_two_additional", len(found) >= A.T26_REQUIRED,
                f"affirmed Additional experiences (besides BOLT): {found}")

    elif number == 27:
        j.check("drink_packages_visited", navigated_path(t, "/drink-packages"),
                "drink packages page")
        j.check("answer_price", affirm_money(fa, A.T27_PRICE), fa)
        j.check("answer_unit", affirms_any(fa, ["per person per day", "person per day",
                                                "per day", "/ person per day"]), fa)

    elif number == 28:
        j.check("contact_us_visited", navigated_path(t, "/about-carnival/contact-us"),
                "Contact Us page")
        j.check("answer_weekend_open", affirm_time(fa, *A.T28_OPEN), fa)
        j.check("answer_weekend_close", affirm_time(fa, *A.T28_CLOSE), fa)
        j.check("answer_timezone", _tz_ok(fa), fa)

    elif number == 29:
        j.check("login_visited", navigated_path(t, "/login"), "logged in as carol")
        j.check("favorites_visited", navigated_path(t, "/favorites"), "favorites page")
        j.check("answer_count", contains_count(fa, A.T29_COUNT), fa)
        j.check("answer_shortest", affirms(fa, A.T29_SHORTEST), fa)

    else:
        j.check("task_exists", False, f"no grading logic for task {number}")

    if emit:
        j.emit()
    return j


# ---------------------------------------------------------------- stateful helpers
def _booking_task(j, t, a, b, fa):
    """Task 13: register + book BAW sailing 22233 (2026-09-25) interior x2 adults."""
    if a is None or b is None:
        j.check("db_available", False, "initial/after DB unavailable")
        return
    j.check("register_visited", navigated_path(t, "/register"), "registration page")
    j.check("booking_flow_visited", navigated_prefix(t, "/booking"), "4-step booking flow")
    new_users = new_rows(b, a, "users")
    j.check("one_new_user", len(new_users) == 1,
            f"new users: {[u['email'] for u in new_users]}")
    if len(new_users) != 1:
        return
    user = new_users[0]
    j.check("new_user_email", user["email"] == A.T13_EMAIL, user["email"])
    j.check("new_user_name", bool((user["first_name"] or "").strip())
            and bool((user["last_name"] or "").strip()),
            f"{user['first_name']!r} {user['last_name']!r}")
    sailing = scalar(b, "sailings", sailing_id=A.T13_SAILING_ID)
    j.check("sailing_anchor", sailing is not None, f"sailing {A.T13_SAILING_ID} in seed")
    j.check("registration_phone", user.get("phone") == "555-0100", "requested contact phone saved")
    new_bookings = new_rows(b, a, "bookings")
    j.check("one_new_booking", len(new_bookings) == 1,
            f"new bookings: {[r['booking_number'] for r in new_bookings]}")
    new_payments = new_rows(b, a, "payment_methods")
    j.check("one_new_payment", len(new_payments) == 1,
            f"new payments: {[(r['card_type'], r['last4']) for r in new_payments]}")
    if len(new_bookings) == 1 and sailing is not None:
        bk = new_bookings[0]
        expect = {
            "user_id": user["id"],
            "sailing_id": sailing["id"],
            "room_type": A.T13_ROOM,
            "room_category": "Interior",
            "guests": A.T13_GUESTS,
            "lead_guest": A.T13_LEAD,
            "status": "confirmed",
        }
        mism = {k: bk[k] for k, v in expect.items() if bk[k] != v}
        j.check("booking_fields", not mism, f"mismatched: {mism}" if mism else str(expect))
        j.check("booking_total", isinstance(bk["total_price"], (int, float))
                and abs(float(bk["total_price"]) - A.T13_TOTAL) < 0.005,
                f"total_price={bk['total_price']!r} (expected {A.T13_TOTAL})")
        j.check("booking_number_format", bool(re.match(r"^CCL[A-Z0-9]{8}$", bk["booking_number"])),
                bk["booking_number"])
        if len(new_payments) == 1:
            pm = new_payments[0]
            pm_expect = {"user_id": user["id"], "card_type": A.T13_CARD_TYPE,
                         "last4": A.T13_CARD_LAST4, "exp_month": 9, "exp_year": 2028}
            pm_mism = {k: pm[k] for k, v in pm_expect.items() if pm[k] != v}
            j.check("payment_fields", not pm_mism,
                    f"mismatched: {pm_mism}" if pm_mism else str(pm_expect))
        j.check("only_requested_booking_changes",
                preserved(b, a,
                          additions={"users": [user["id"]],
                                     "bookings": [bk["id"]],
                                     "payment_methods": [r["id"] for r in new_payments]}),
                "no unrelated table/row changes")
        j.check("answer_booking_number", affirms(fa, bk["booking_number"]),
                f"booking number {bk['booking_number']} reported")
    j.check("answer_total", affirm_money(fa, A.T13_TOTAL), fa)


def _excursion_task(j, t, a, b, fa):
    """Task 17: alice adds Pearl Cove Beach Club (2 guests) to booking 9N382702."""
    if a is None or b is None:
        j.check("db_available", False, "initial/after DB unavailable")
        return
    j.check("login_visited", navigated_path(t, "/login"), "logged in as alice")
    j.check("booking_detail_visited", navigated_path(t, f"/booked/manage/{A.T17_BOOKING}"),
            f"booking {A.T17_BOOKING} detail")
    seed_booking = _booking_row(b, "seed", A.T17_BOOKING)
    j.check("booking_anchor", seed_booking is not None,
            f"booking {A.T17_BOOKING} in seed")
    if seed_booking is None:
        return
    new_excs = new_rows(b, a, "booking_excursions")
    j.check("one_new_excursion_row", len(new_excs) == 1,
            f"new booking_excursions rows: {new_excs}")
    excursion = scalar(b, "excursions", code=A.T17_EXCURSION_CODE)
    j.check("excursion_anchor", excursion is not None,
            f"excursion {A.T17_EXCURSION_CODE} in seed")
    after_booking = _booking_row(a, "after", A.T17_BOOKING)
    j.check("total_updated", after_booking is not None
            and abs(float(after_booking["total_price"]) - A.T17_NEW_TOTAL) < 0.005,
            f"total_price={after_booking['total_price'] if after_booking else None!r} "
            f"(expected {A.T17_NEW_TOTAL})")
    if len(new_excs) == 1 and excursion is not None:
        be = new_excs[0]
        expect = {"booking_id": seed_booking["id"], "excursion_id": excursion["id"],
                  "guests": A.T17_EXC_GUESTS}
        mism = {k: be[k] for k, v in expect.items() if be[k] != v}
        j.check("excursion_row_fields", not mism,
                f"mismatched: {mism}" if mism else str(expect))
        j.check("excursion_row_price", abs(float(be["price"]) - A.T17_EXC_PRICE) < 0.005,
                f"price={be['price']!r} (expected {A.T17_EXC_PRICE})")
        j.check("only_requested_excursion_changes",
                preserved(b, a,
                          changes={"bookings": {seed_booking["id"]: {"total_price"}}},
                          additions={"booking_excursions": [be["id"]]}),
                "no unrelated table/row changes")
    j.check("answer_booking", contains_any(fa, [A.T17_BOOKING, A.T17_BOOKING.lower()]), fa)
    j.check("answer_new_total", affirm_money(fa, A.T17_NEW_TOTAL), fa)
