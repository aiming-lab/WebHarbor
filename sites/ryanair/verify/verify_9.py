#!/usr/bin/env python3
"""Verify Ryanair--9.

My friend lost his booking emails. Look up booking M9D2XV with email bob.c@test.com on the My bookings page. Report the outbound flight number, its departure time, the return departure time, how many passengers are on it and the total paid. Then check the help centre: report the 20kg check-in bag price online versus at the airport, the cheapest extra-legroom seat price from the seats article, and whether online check-in has opened for this booking yet, and why.
"""
from verify_lib import (Judge, booking_by_ref, check_read_only, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_count, contains_phrase,
                        contains_time, final_answer, navigated_to_path, run_verifier,
                        schedule_of)

TASK_ID = "Ryanair--9"
REF = "M9D2XV"
EMAIL = "bob.c@test.com"
OUT_FLIGHT = "FR 540"
OUT_DEP = "20:35"
IN_DEP = "13:10"
PAX = 2
TOTAL = 95.84
BAG_ONLINE = 25.49
BAG_AIRPORT = 50.00
XL_CHEAPEST = 14.50


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # guest lookup on My bookings
    check_visited_path(judge, traj, "visited_my_bookings", "/gb/en/my-bookings")
    check_visited_path(judge, traj, "visited_booking_detail", f"/gb/en/booking/{REF}")
    check_visited_path(judge, traj, "visited_help_checkin_bags", "/gb/en/r/help/checkin-bags")
    check_visited_path(judge, traj, "visited_help_seats", "/gb/en/r/help/seats")
    check_visited_path(judge, traj, "visited_checkin_page", f"/gb/en/check-in/{REF}")
    # booking facts
    judge.check("answer_out_flight", contains_phrase(answer, OUT_FLIGHT),
                f"expected outbound flight {OUT_FLIGHT}")
    judge.check("answer_out_dep_time", contains_time(answer, OUT_DEP),
                f"expected outbound departure {OUT_DEP}")
    judge.check("answer_return_dep_time", contains_time(answer, IN_DEP),
                f"expected return departure {IN_DEP}")
    judge.check("answer_passengers", contains_count(answer, PAX),
                f"expected {PAX} passengers")
    judge.check("answer_total_paid", contains_amount(answer, TOTAL),
                f"expected total paid £{TOTAL:.2f}")
    # help centre facts
    judge.check("answer_bag_online_25_49", contains_amount(answer, BAG_ONLINE),
                f"expected 20kg online price £{BAG_ONLINE:.2f}")
    judge.check("answer_bag_airport_50", contains_amount(answer, BAG_AIRPORT),
                f"expected 20kg airport price £{BAG_AIRPORT:.2f}")
    judge.check("answer_cheapest_xl_14_50", contains_amount(answer, XL_CHEAPEST),
                f"expected cheapest extra-legroom seat £{XL_CHEAPEST:.2f}")
    judge.check("answer_checkin_not_open",
                contains_phrase(answer, "not opened") or contains_phrase(answer, "not open")
                or contains_phrase(answer, "hasn't opened") or contains_phrase(answer, "has not opened"),
                "answer must state online check-in has NOT opened yet")
    judge.check("answer_why_24h_random",
                contains_phrase(answer, "24 hours") or contains_phrase(answer, "24 hour"),
                "answer must explain the 24-hour window (randomly allocated seats)")
    # booking is intact and unchanged
    bk = booking_by_ref(after_db, REF)
    judge.check("booking_untouched", bk is not None and not bk["checked_in"]
                and abs(bk["total"] - TOTAL) < 0.011,
                f"booking={bk and (bk['checked_in'], bk['total'])!r}")
    check_read_only(judge, initial_db, after_db)


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
