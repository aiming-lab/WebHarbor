#!/usr/bin/env python3
"""Verify Marriott--4.

Orlando family stay 12/18/2026-12/21/2026, one room, four guests: at the cheapest
Orlando hotel by nightly rate, book its cheapest room type that sleeps at least
four guests, for guest Dana Brooks with Mastercard 5200828282828220 exp 10/2027.
Report the room type name, the total, and the confirmation number.

Frozen ground truth (seed DB): cheapest Orlando hotel = Courtyard by Marriott
Orlando Downtown (marsha MCOMA, base rate $160); its cheapest room type sleeping
4+ = Guest Room, 2 Double Beds at $175/night; 3 nights -> $525.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_trajectory_identity, contains_amount,
                        contains_phrase, final_answer, navigated_availability, navigated_confirmation,
                        navigated_find_hotels, navigated_gateway, run_verifier)

TASK_ID = "Marriott--4"
HOTEL = "Courtyard by Marriott Orlando Downtown"
MARSHA = "MCOMA"
ROOM = "Guest Room, 2 Double Beds"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_orlando_search", navigated_find_hotels(traj, "Orlando"),
                "required: /search/findHotels.mi with destinationAddress containing 'Orlando'")
    judge.check("visited_courtyard_availability", navigated_availability(traj, MARSHA),
                f"required: /reservation/availabilitySearch.mi?propertyCode={MARSHA}")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    judge.check("answer_room_type", contains_phrase(answer, "Guest Room, 2 Double Beds"),
                "expected the room type name: Guest Room, 2 Double Beds")
    judge.check("answer_total", contains_amount(answer, 525),
                "expected total $525 (3 nights x $175)")
    added = added_reservation_matching(after_db, initial_db,
                                       hotel_name=HOTEL, room_name=ROOM,
                                       guest_first_name="Dana", guest_last_name="Brooks",
                                       guest_email="dana.brooks@example.com",
                                       checkin="2026-12-18", checkout="2026-12-21",
                                       nightly_rate=175, total_rate=525,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {HOTEL}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "booking")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
