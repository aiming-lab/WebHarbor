#!/usr/bin/env python3
"""Verify Marriott--0.

Two-night San Francisco escape 11/06/2026-11/08/2026, two adults, one room: among
hotels rated 4.0+, reserve the most affordable one in its cheapest available room
type for guest Jordan Ellis, card 4012888888881881 exp 11/2029. Report the
confirmation number and the total shown on the confirmation page.

Frozen ground truth (seed DB): cheapest rated-4.0+ San Francisco hotel =
citizenM San Francisco Union Square (marsha SFOFU, base rate $170); its cheapest
room type = Guest Room, 1 King Bed at $170/night; 2 nights -> $340 total.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_trajectory_identity, check_visited_path,
                        contains_amount, final_answer, navigated_availability, navigated_confirmation,
                        navigated_find_hotels, navigated_gateway, run_verifier)

TASK_ID = "Marriott--0"
HOTEL = "citizenM San Francisco Union Square"
MARSHA = "SFOFU"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # navigation gates: destination search, the target hotel's availability, the
    # booking gateway, and the confirmation page
    judge.check("visited_sf_search", navigated_find_hotels(traj, "San Francisco"),
                "required: /search/findHotels.mi with destinationAddress containing 'San Francisco'")
    judge.check("visited_citizenm_availability", navigated_availability(traj, MARSHA),
                f"required: /reservation/availabilitySearch.mi?propertyCode={MARSHA}")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    # answer: confirmation number + total from the confirmation page
    judge.check("answer_total", contains_amount(answer, 340),
                "expected total $340 (2 nights x $170)")
    # DB after-state: exactly one reservation added for the right hotel/room/dates/
    # guest/total, and nothing else changed
    added = added_reservation_matching(after_db, initial_db,
                                       user_id=None, rooms=1, adults=2, children=0,
                                       hotel_name=HOTEL,
                                       room_name="Guest Room, 1 King Bed",
                                       guest_first_name="Jordan", guest_last_name="Ellis",
                                       guest_email="jordan.ellis@example.com",
                                       checkin="2026-11-06", checkout="2026-11-08",
                                       nightly_rate=170, total_rate=340,
                                       points_redeemed=0, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added reservation row for {HOTEL}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "booking")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
