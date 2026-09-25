#!/usr/bin/env python3
"""Verify Marriott--14.

Boston getaway 11/13/2026-11/15/2026, two guests, one room: from the Boston
destination page identify how many Marriott Bonvoy hotels it lists and pick the
cheapest per night; check that hotel's reviews page and report its average rating
and total review count; then book its cheapest room type for guest Alex Foley
with Amex 378282246310005 exp 06/2028; report the total and confirmation number.

Frozen ground truth (seed DB): the Boston destination page lists 12 hotels; the
cheapest per night = Moxy Boston Downtown (marsha BOSOX, cheapest room Guest
Room, 1 King Bed at $360/night); reviews: average 3.8, 1,444 reviews; booking
2 nights -> $720 total.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_count, contains_phrase, final_answer,
                        navigated_availability, navigated_confirmation, navigated_destination_page,
                        navigated_find_hotels, navigated_gateway, navigated_hotel_tab, run_verifier)

TASK_ID = "Marriott--14"
HOTEL = "Moxy Boston Downtown"
MARSHA = "BOSOX"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_boston_destination_page", navigated_destination_page(traj, "boston"),
                "required: the Boston destination page (/en-us/destinations/...boston...)")
    judge.check("visited_boston_search",
                navigated_find_hotels(traj, "Boston") or navigated_destination_page(traj, "boston"),
                "required: a Boston hotel surface — either /search/findHotels.mi with "
                "destinationAddress containing 'Boston' or the Boston destination page "
                "(the task counts and prices the destination page itself lists)")
    judge.check("visited_reviews_page", navigated_hotel_tab(traj, "reviews", "moxy-boston-downtown"),
                "required: the cheapest Boston hotel's reviews page")
    judge.check("visited_availability",
                navigated_availability(traj, MARSHA)
                or navigated_hotel_tab(traj, "rooms", "moxy-boston-downtown"),
                f"required: the booked hotel's rooms surface — either "
                f"/reservation/availabilitySearch.mi?propertyCode={MARSHA} or its "
                f"/en-us/hotels/<ident>/rooms/ tab")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    judge.check("answer_hotel_count", contains_count(answer, 12),
                "expected the Boston destination page's hotel count: 12")
    judge.check("answer_hotel_name", contains_phrase(answer, "Moxy Boston Downtown"),
                "expected the cheapest Boston hotel: Moxy Boston Downtown")
    judge.check("answer_avg_rating", contains_amount(answer, 3.8),
                "expected average rating 3.8")
    judge.check("answer_review_count", contains_amount(answer, 1444),
                "expected total review count 1,444")
    judge.check("answer_total", contains_amount(answer, 720),
                "expected booking total $720 (2 nights x $360)")
    added = added_reservation_matching(after_db, initial_db,
                                       user_id=None, rooms=1, adults=2, children=0,
                                       hotel_name=HOTEL, room_name="Guest Room, 1 King Bed",
                                       guest_first_name="Alex", guest_last_name="Foley",
                                       guest_email="alex.foley@example.com",
                                       checkin="2026-11-13", checkout="2026-11-15",
                                       nightly_rate=360, total_rate=720,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {HOTEL}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "booking")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
