#!/usr/bin/env python3
"""Verify Megabus--18.

Check whether SAVE20 really takes $20 off my cheapest New York-to-Philadelphia trip on October 3rd. Add the trip to the basket and try the code; if it fails, find the promotion advertised in the fare finder and apply that instead. Report whether SAVE20 worked, the code applied, and the basket total with and without text-message travel updates. Leave the booking unpaid.
"""
from verify_lib import (Judge, basket_rows, check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_phrase, final_answer,
                        navigated_journeys, run_verifier, db_query)

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
    # DB after-state: one basket row for the cheapest journey, no booking created
    rows = basket_rows(after_db)
    judge.check("basket_has_one_item", len(rows) == 1, f"basket_rows={rows!r}")
    if rows:
        judge.check("basket_item_is_cheapest",
                    abs(rows[0]["unit_price"] - CHEAPEST) < 0.011 and rows[0]["passengers"] == 1,
                    f"unit_price={rows[0]['unit_price']!r}, passengers={rows[0]['passengers']!r}")
    if rows:
        journey = db_query(after_db, "SELECT origin_city_id,dest_city_id,departure_date,price FROM journeys WHERE id=?", (rows[0]['journey_id'],))
        judge.check('basket_route_date', bool(journey) and journey[0]['origin_city_id']==123 and journey[0]['dest_city_id']==127 and journey[0]['departure_date']=='2026-10-03' and abs(journey[0]['price']-CHEAPEST)<0.011, 'basket must contain the requested route and date')
    check_only_tables_changed(judge, initial_db, after_db, ("basket_items",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
