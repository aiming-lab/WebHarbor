#!/usr/bin/env python3
"""Verify Marriott--18.

Sign in as david.k@test.com. Compare the most expensive room types at The Westin
New York Grand Central and Residence Inn by Marriott New York Manhattan/Times
Square: report which hotel's top room type costs more per night and by how many
dollars, plus the bed setup and square footage of the cheaper of the two top
rooms; then redeem points for one night, 10/30/2026-10/31/2026, in that cheaper
top room and report the confirmation number and your remaining points balance.

Frozen ground truth (seed DB): Westin top room = Premium Suite, 1 King Bed, High
Floor at $1,175/night (marsha NYCZW); Residence Inn Times Square top room =
Premium Suite, 1 King Bed, High Floor at $1,200/night (marsha NYCRI) — the
Residence Inn's top room costs $25 more; the cheaper top room (Westin) has
1 king bed + sofa bed, 720 sq ft; redeeming one night = 117,500 points; david's
seed balance 274,900 - 117,500 = 157,400.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        contains_amount, contains_count, contains_phrase, navigated_to_path_any,
                        final_answer, navigated_availability, navigated_confirmation, navigated_find_hotels,
                        navigated_gateway, navigated_hotel_tab, run_verifier, user_by_email)

TASK_ID = "Marriott--18"
WES = ("The Westin New York Grand Central", "NYCZW", "the-westin-new-york-grand-central")
RES = ("Residence Inn by Marriott New York Manhattan/Times Square", "NYCRI",
       "residence-inn-new-york-manhattan-times-square")
ROOM = "Premium Suite, 1 King Bed, High Floor"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "david.k@test.com")
    judge.check("visited_nyc_search", navigated_find_hotels(traj, "New York"),
                "required: /search/findHotels.mi with destinationAddress containing 'New York'")
    judge.check("visited_wes_rooms",
                navigated_hotel_tab(traj, "rooms", WES[2]) or navigated_availability(traj, WES[1]),
                "required: The Westin New York Grand Central rooms page")
    judge.check("visited_res_rooms",
                navigated_hotel_tab(traj, "rooms", RES[2]) or navigated_availability(traj, RES[1]),
                "required: Residence Inn Times Square rooms page")
    judge.check("visited_gateway", navigated_gateway(traj, WES[1], with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    judge.check("visited_account_page",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account page (either route alias)")
    # answer facts
    judge.check("answer_pricier_verdict", contains_phrase(answer, "Residence Inn"),
                "the Residence Inn Times Square top room ($1,200) costs more per night")
    judge.check("answer_price_gap", contains_amount(answer, 25),
                "expected the $25/night gap ($1,200 vs $1,175)")
    judge.check("answer_cheaper_top_room", contains_phrase(answer, ROOM),
                "expected the cheaper top room's name: Premium Suite, 1 King Bed, High Floor (Westin)")
    judge.check("answer_bed_setup", contains_phrase(answer, "1 king bed"),
                "expected the cheaper top room's bed setup '1 king bed + sofa bed'")
    judge.check("answer_sqft", contains_count(answer, 720),
                "expected the cheaper top room's 720 sq ft")
    judge.check("answer_remaining_balance", contains_amount(answer, 157400),
                "expected remaining points balance 157,400")
    # DB after-state: david's points debited; one points reservation added
    david = user_by_email(after_db, "david.k@test.com")
    judge.check("david_points_debited", david and david["points"] == 157400,
                f"expected david points=157400, observed={david and david['points']}")
    added = added_reservation_matching(after_db, initial_db,
                                       user_id=4, rooms=1, adults=1, children=0,
                                       hotel_name=WES[0], room_name=ROOM,
                                       guest_first_name="David", guest_last_name="Kim",
                                       guest_email="david.k@test.com",
                                       checkin="2026-10-30", checkout="2026-10-31",
                                       nightly_rate=1175, total_rate=117500,
                                       points_redeemed=117500, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added points reservation for {WES[0]} / {ROOM}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "redemption")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations", "users"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
