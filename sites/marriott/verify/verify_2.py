#!/usr/bin/env python3
"""Verify Marriott--2.

Denver work trip 12/01/2026-12/04/2026: book the cheapest Denver hotel whose
amenity listing includes a Fitness Center, in its cheapest room type, for guest
Priya Nair with Visa 4500123456789012 exp 08/2028. Report the hotel's name and the
confirmation number.

Frozen ground truth (seed DB): cheapest Denver hotel with a Fitness Center =
Magnolia Hotel Denver, a Tribute Portfolio Hotel (marsha DENMG, base $189); its
cheapest room type = Guest Room, 1 King Bed at $190/night; 3 nights -> $570.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_trajectory_identity, contains_phrase,
                        final_answer, navigated_availability, navigated_confirmation,
                        navigated_find_hotels, navigated_gateway, run_verifier)

TASK_ID = "Marriott--2"
HOTEL = "Magnolia Hotel Denver, a Tribute Portfolio Hotel"
MARSHA = "DENMG"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_denver_search", navigated_find_hotels(traj, "Denver"),
                "required: /search/findHotels.mi with destinationAddress containing 'Denver'")
    judge.check("visited_magnolia_availability", navigated_availability(traj, MARSHA),
                f"required: /reservation/availabilitySearch.mi?propertyCode={MARSHA}")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    judge.check("answer_hotel_name", contains_phrase(answer, "Magnolia Hotel Denver"),
                "expected the hotel name: Magnolia Hotel Denver, a Tribute Portfolio Hotel")
    added = added_reservation_matching(after_db, initial_db,
                                       hotel_name=HOTEL,
                                       room_name="Guest Room, 1 King Bed",
                                       guest_first_name="Priya", guest_last_name="Nair",
                                       guest_email="priya.nair@example.com",
                                       checkin="2026-12-01", checkout="2026-12-04",
                                       nightly_rate=190, total_rate=570,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {HOTEL}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "booking")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
