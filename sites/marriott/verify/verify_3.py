#!/usr/bin/env python3
"""Verify Marriott--3.

New York City 10/20/2026-10/22/2026, one room: compare the two cheapest hotels
rated 4.0+ by opening their rooms pages and noting each one's cheapest room type
rate; reserve the option with the lower two-night total for guest Sam Carter with
card 5555666677778888 exp 03/2029. Report which hotel you booked, the total,
and the confirmation number.

Frozen ground truth (seed DB): two cheapest rated-4.0+ NYC hotels =
SpringHill Suites by Marriott New York Midtown Manhattan/Fifth Avenue (marsha
NYCSM, cheapest room $410/night) and Courtyard by Marriott New York Manhattan/
Times Square (marsha NYCMD, cheapest room $445/night); lower two-night total =
SpringHill at $820.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_trajectory_identity, contains_amount,
                        contains_phrase, final_answer, navigated_availability, navigated_confirmation,
                        navigated_find_hotels, navigated_gateway, navigated_hotel_tab, run_verifier)

TASK_ID = "Marriott--3"
WINNER = "SpringHill Suites by Marriott New York Midtown Manhattan/Fifth Avenue"
WINNER_MARSHA = "NYCSM"
RUNNER_UP_MARSHA = "NYCMD"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_nyc_search", navigated_find_hotels(traj, "New York"),
                "required: /search/findHotels.mi with destinationAddress containing 'New York'")
    WINNER_SLUG = "springhill-suites-new-york-midtown-manhattan-fifth-avenue"
    RUNNER_UP_SLUG = "courtyard-new-york-manhattan-times-square"
    two_compared = all(
        navigated_availability(traj, m) or navigated_hotel_tab(traj, "rooms", s)
        for m, s in ((WINNER_MARSHA, WINNER_SLUG), (RUNNER_UP_MARSHA, RUNNER_UP_SLUG)))
    judge.check("visited_both_rooms_pages", two_compared,
                f"required: each compared hotel's rooms surface — either "
                f"/reservation/availabilitySearch.mi?propertyCode=<marsha> or its "
                f"/en-us/hotels/<ident>/rooms/ tab — for both {WINNER_MARSHA} and {RUNNER_UP_MARSHA}")
    judge.check("visited_gateway", navigated_gateway(traj, WINNER_MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    judge.check("answer_booked_hotel", contains_phrase(answer, "SpringHill Suites"),
                "expected the booked hotel: SpringHill Suites by Marriott New York Midtown Manhattan/Fifth Avenue")
    judge.check("answer_total", contains_amount(answer, 820),
                "expected total $820 (2 nights x $410)")
    added = added_reservation_matching(after_db, initial_db,
                                       hotel_name=WINNER,
                                       room_name="Guest Room, 1 King Bed",
                                       guest_first_name="Sam", guest_last_name="Carter",
                                       guest_email="sam.carter@example.com",
                                       checkin="2026-10-20", checkout="2026-10-22",
                                       nightly_rate=410, total_rate=820,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {WINNER}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "booking")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
