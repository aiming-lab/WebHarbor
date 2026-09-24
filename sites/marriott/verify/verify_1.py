#!/usr/bin/env python3
"""Verify Marriott--1.

Sign in as alice.j@test.com. Points-rate search for Chicago, 10/30/2026-10/31/2026,
one room, one adult: redeem Bonvoy points for the stay with the lowest nightly
points rate, booking its cheapest room type for yourself. Report the confirmation
number, the points redeemed, and your remaining points balance on your account page.

Frozen ground truth (seed DB): lowest Chicago nightly points rate = The Westin
Chicago River North (marsha CHINO) at 19,000 points/night; cheapest room =
Guest Room, 1 King Bed ($190/night, 19,000 pts); alice's seed balance
148,350 - 19,000 = 129,350.
"""
from verify_lib import (Judge, added_reservation_matching, check_answer_conf_matches_added_reservation,
                        check_only_tables_changed, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, final_answer, navigated_to_path_any, navigated_availability,
                        navigated_confirmation, navigated_find_hotels, navigated_gateway,
                        run_verifier, user_by_email)

TASK_ID = "Marriott--1"
HOTEL = "The Westin Chicago River North"
MARSHA = "CHINO"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    judge.check("visited_points_search", navigated_find_hotels(traj, "Chicago",
                 {"useRewardsPoints": "true"}),
                "required: /search/findHotels.mi destinationAddress=Chicago&useRewardsPoints=true")
    judge.check("visited_westin_availability", navigated_availability(traj, MARSHA),
                f"required: /reservation/availabilitySearch.mi?propertyCode={MARSHA}")
    judge.check("visited_gateway", navigated_gateway(traj, MARSHA, with_room=True),
                "required: /reservation/reservationGateway.mi with propertyCode + roomId")
    judge.check("visited_confirmation", navigated_confirmation(traj),
                "required: /reservation/confirmation.mi")
    judge.check("visited_account_page",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account page (either route alias)")
    # answer: conf number, points redeemed, remaining balance
    judge.check("answer_points_redeemed", contains_amount(answer, 19000),
                "expected 19,000 points redeemed")
    judge.check("answer_remaining_balance", contains_amount(answer, 129350),
                "expected remaining balance 129,350")
    # DB after-state: alice's points debited; one points reservation added
    alice = user_by_email(after_db, "alice.j@test.com")
    judge.check("alice_points_debited", alice and alice["points"] == 129350,
                f"expected alice points=129350, observed={alice and alice['points']}")
    added = added_reservation_matching(after_db, initial_db,
                                       hotel_name=HOTEL,
                                       room_name="Guest Room, 1 King Bed",
                                       guest_first_name="Alice", guest_last_name="Johnson",
                                       guest_email="alice.j@test.com",
                                       checkin="2026-10-30", checkout="2026-10-31",
                                       nightly_rate=190, total_rate=19000,
                                       points_redeemed=19000, status="confirmed")
    judge.check("added_reservation_row", added is not None,
                f"expected one added points reservation for {HOTEL}; found={added!r}")
    check_answer_conf_matches_added_reservation(judge, answer, added, "booking")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations", "users"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
