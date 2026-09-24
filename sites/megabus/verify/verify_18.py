#!/usr/bin/env python3
"""Verify Megabus--18.

Add the cheapest New York→Philadelphia trip on Oct 3 to the basket, try the
code SAVE20; if it fails, find the promotion megabus actually advertises, apply
it instead, and report the final total shown in the basket before paying.

Frozen ground truth (seed DB): NY→PHL 2026-10-03 cheapest = $25.99 (00:00
departure). SAVE20 is not in promo_codes → the basket shows "The code SAVE20
is not valid." The advertised code is EMAIL5 (disclosed on /fare-finder):
$5.00 off bookings over $15.00. The fare finder with origin New York lists
Newark, NJ as the cheapest destination from $13.50. Final basket total =
25.99 − 5.00 + 3.99 booking fee = $24.98; with the $0.25 text message travel
updates option enabled the basket total = $25.23. The DB delta is the
basket_items row (session-scoped promo/SMS flags are not persisted); no
booking may be created.
"""
from verify_lib import (Judge, basket_rows, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_journeys, run_verifier)

TASK_ID = "Megabus--18"
NY_ID, PHL_ID = 123, 127
CHEAPEST = 25.99
FINAL_TOTAL = 24.98
SMS_TOTAL = 25.23
FF_CHEAPEST_DEST = "Newark"
FF_CHEAPEST_FARE = 13.50


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_journeys_results",
                navigated_journeys(traj, NY_ID, PHL_ID, "2026-10-03"),
                "required: journeys NY→PHL on 2026-10-03")
    check_visited_path(judge, traj, "visited_basket", "/journey-planner/basket")
    check_visited_path(judge, traj, "visited_fare_finder", "/fare-finder")
    judge.check("visited_fare_finder_ny_search",
                any("/fare-finder/search" in u and "originId=123" in u
                    for u in [str(s.get("url", "")) for s in traj.get("steps") or [] if isinstance(s, dict)]),
                "required: /fare-finder/search?originId=123 (New York)")
    judge.check("answer_save20_rejected",
                contains_phrase(answer, "not valid") or contains_phrase(answer, "rejected")
                or contains_phrase(answer, "didn't work") or contains_phrase(answer, "failed"),
                "expected SAVE20 to be reported as rejected/invalid")
    judge.check("answer_email5_applied", contains_phrase(answer, "EMAIL5"),
                "expected the advertised code EMAIL5 to be applied instead")
    judge.check("answer_final_total", contains_amount(answer, FINAL_TOTAL),
                f"expected final basket total ${FINAL_TOTAL} (25.99 − 5.00 + 3.99)")
    judge.check("answer_sms_total", contains_amount(answer, SMS_TOTAL),
                f"expected the with-SMS basket total ${SMS_TOTAL} (24.98 + 0.25)")
    judge.check("answer_fare_finder_cheapest_dest",
                contains_phrase(answer, FF_CHEAPEST_DEST) and contains_amount(answer, FF_CHEAPEST_FARE),
                "expected the fare finder's cheapest destination from New York: Newark from $13.50")
    # DB after-state: one basket row for the cheapest journey, no booking created
    rows = basket_rows(after_db)
    judge.check("basket_has_one_item", len(rows) == 1, f"basket_rows={rows!r}")
    if rows:
        judge.check("basket_item_is_cheapest",
                    abs(rows[0]["unit_price"] - CHEAPEST) < 0.011 and rows[0]["passengers"] == 1,
                    f"unit_price={rows[0]['unit_price']!r}, passengers={rows[0]['passengers']!r}")
    check_only_tables_changed(judge, initial_db, after_db, ("basket_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
