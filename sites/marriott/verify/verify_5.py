#!/usr/bin/env python3
"""Sign in as alice.j@test.com (password TestPass123!). My Atlanta trip under Alice Johnson, confirmation ACCEDGHDDR, has fallen through. Find that reservation and cancel it, leaving my other trips unchanged. Tell me which hotel, room and check-in date you canceled, the reservation total, and whether the cancellation is confirmed."""
from verify_lib import (Judge, canceled_among, check_only_tables_changed, check_signed_in_as,
                        check_trajectory_identity, contains_amount, navigated_to_path_any,
                        contains_any, contains_date_phrase, contains_phrase, contains_slash_date,
                        contains_time, final_answer, navigated_hotel_overview, navigated_to,
                        run_verifier)

TASK_ID = "Marriott--5"
CONF = "ACCEDGHDDR"
HOTEL = "Courtyard by Marriott Atlanta Downtown"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "alice.j@test.com")
    judge.check("visited_account_trips",
                navigated_to_path_any(traj, ["/loyalty/myAccount.mi", "/account"]),
                "required: the account/trips page (either route alias)")
    # answer: check-in time + lookup facts + post-cancel status
    judge.check("answer_hotel", contains_phrase(answer, "Courtyard by Marriott Atlanta Downtown"),
                "expected the hotel name")
    judge.check("answer_room_type", contains_phrase(answer, "Guest Room, 1 King Bed"),
                "expected room type Guest Room, 1 King Bed")
    judge.check("answer_checkin_date",
                contains_date_phrase(answer, "November 2, 2026") or contains_slash_date(answer, 11, 2, 2026),
                "expected check-in date Nov 02, 2026")
    judge.check("answer_total", contains_amount(answer, 290),
                "expected total $290")
    judge.check("answer_canceled_status", contains_any(answer, ["canceled", "cancelled"]),
                "expected the post-cancel status to be reported as Canceled")
    # DB after-state: exactly the ACCEDGHDDR status flip, nothing else
    judge.check("accedghddr_canceled", canceled_among(initial_db, after_db, CONF),
                f"expected {CONF} status confirmed -> canceled")
    check_only_tables_changed(judge, initial_db, after_db, ("reservations",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
