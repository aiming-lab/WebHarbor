#!/usr/bin/env python3
"""Verify Marriott--7.

Sign in as bob.c@test.com. Open the upcoming trip's hotel and report the trip's
check-in date, room type, and total; from the hotel page report its exact street
address, the phone number in the header, and whether the amenity list includes a
fitness center; visit the reviews page and report the average rating and the title
of the most recent review; then extend the stay by booking that hotel's cheapest
room type for 10/18/2026-10/20/2026 under guest Bob Chen with card 5242882882828282
exp 04/2029, and report the confirmation number and total.

Frozen ground truth (seed DB): bob's upcoming trip = GQQMABBHHD at AC Hotel Atlanta
Downtown (marsha ATLAR), 10/18/2026, Guest Room, 1 King Bed, $170; hotel address
101 Andrew Young Intl Blvd NW, phone +14045245555, Fitness Center amenity present;
average rating 4.1; most recent review title "Great place"; extension books the
same cheapest room 2 nights -> $340.
"""
import re

from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        contains_amount, contains_date_phrase, contains_phrase, navigated_to_path_any,
                        contains_slash_date, final_answer, navigated_availability, navigated_confirmation,
                        navigated_find_hotels, navigated_gateway, navigated_hotel_overview,
                        navigated_hotel_tab, norm, run_verifier)

TASK_ID = "Marriott--7"
HOTEL = "AC Hotel Atlanta Downtown"
MARSHA = "ATLAR"


def _phone_digits(answer):
    return re.sub(r"\D", "", norm(answer))


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    judge.check("visited_account_trips",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account/trips page (either route alias)")
    judge.check("visited_hotel_overview", navigated_hotel_overview(traj, "ac-hotel-atlanta-downtown"),
                "required: AC Hotel Atlanta Downtown overview page")
    judge.check("visited_reviews_page", navigated_hotel_tab(traj, "reviews", "ac-hotel-atlanta-downtown"),
                "required: the hotel's reviews tab")
    judge.check("visited_availability_for_extension",
                navigated_availability(traj, MARSHA)
                or navigated_hotel_tab(traj, "rooms", "ac-hotel-atlanta-downtown"),
                f"required: the hotel's rooms surface for the extension — either "
                f"/reservation/availabilitySearch.mi?propertyCode={MARSHA} or its "
                f"/en-us/hotels/<ident>/rooms/ tab (the reservation row's dates "
                f"carry the extension window)")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    # answer facts
    judge.check("answer_trip_checkin",
                contains_date_phrase(answer, "October 18, 2026") or contains_slash_date(answer, 10, 18, 2026),
                "expected trip check-in date Oct 18, 2026")
    judge.check("answer_trip_room_and_total",
                contains_phrase(answer, "Guest Room, 1 King Bed") and contains_amount(answer, 170),
                "expected trip room type Guest Room, 1 King Bed and total $170")
    judge.check("answer_street_address", contains_phrase(answer, "101 Andrew Young Intl Blvd NW"),
                "expected street address 101 Andrew Young Intl Blvd NW")
    judge.check("answer_phone", "4045245555" in _phone_digits(answer),
                "expected the hotel phone +1 404-524-5555 (digits 4045245555)")
    judge.check("answer_fitness_center", contains_phrase(answer, "Fitness Center"),
                "expected the fitness-center amenity to be reported (present on the hotel page)")
    judge.check("answer_avg_rating", contains_amount(answer, 4.1),
                "expected average rating 4.1")
    judge.check("answer_recent_review_title", contains_phrase(answer, "Great place"),
                "expected most recent review title 'Great place'")
    judge.check("answer_extension_total", contains_amount(answer, 340),
                "expected extension total $340 (2 nights x $170)")
    # DB after-state: one extension reservation added under bob's account
    added = added_reservation_matching(after_db, initial_db,
                                       hotel_name=HOTEL, room_name="Guest Room, 1 King Bed",
                                       guest_first_name="Bob", guest_last_name="Chen",
                                       guest_email="bob.c@test.com",
                                       checkin="2026-10-18", checkout="2026-10-20",
                                       nightly_rate=170, total_rate=340,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {HOTEL}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "extension")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
