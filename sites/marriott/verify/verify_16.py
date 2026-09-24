#!/usr/bin/env python3
"""Verify Marriott--16.

Open the rooms page of The Westin New York Grand Central: report the name, square
footage, bed setup, and nightly rate of its largest room type by size, and how
many room types the hotel lists in total. Then, for 11/13/2026-11/15/2026, book
that largest room type for guest Robin Stone with Visa 4000056655665556 exp
02/2029 and report the total and the confirmation number.

Frozen ground truth (seed DB): The Westin New York Grand Central (marsha NYCZW)
lists 5 room types; the largest by size = Premium Suite, 1 King Bed, High Floor
(720 sq ft, 1 king bed + sofa bed, $1,175/night); 2 nights -> $2,350 total.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_trajectory_identity, contains_amount,
                        contains_count, contains_phrase, final_answer, navigated_confirmation,
                        navigated_find_hotels, navigated_gateway, navigated_hotel_tab, run_verifier)

TASK_ID = "Marriott--16"
HOTEL = "The Westin New York Grand Central"
MARSHA = "NYCZW"
ROOM = "Premium Suite, 1 King Bed, High Floor"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_nyc_search", navigated_find_hotels(traj, "New York"),
                "required: /search/findHotels.mi with destinationAddress containing 'New York'")
    judge.check("visited_rooms_page", navigated_hotel_tab(traj, "rooms", "the-westin-new-york-grand-central"),
                "required: The Westin New York Grand Central rooms page")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    judge.check("answer_largest_room", contains_phrase(answer, ROOM),
                f"expected the largest room type: {ROOM}")
    judge.check("answer_sqft", contains_count(answer, 720),
                "expected 720 sq ft")
    judge.check("answer_bed_setup", contains_phrase(answer, "1 king bed"),
                "expected the bed setup '1 king bed + sofa bed'")
    judge.check("answer_nightly_rate", contains_amount(answer, 1175),
                "expected the $1,175/night rate")
    judge.check("answer_room_type_count", contains_count(answer, 5),
                "expected 5 room types in total")
    judge.check("answer_total", contains_amount(answer, 2350),
                "expected booking total $2,350 (2 nights x $1,175)")
    added = added_reservation_matching(after_db, initial_db,
                                       hotel_name=HOTEL, room_name=ROOM,
                                       guest_first_name="Robin", guest_last_name="Stone",
                                       guest_email="robin.stone@example.com",
                                       checkin="2026-11-13", checkout="2026-11-15",
                                       nightly_rate=1175, total_rate=2350,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {HOTEL} / {ROOM}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "booking")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
