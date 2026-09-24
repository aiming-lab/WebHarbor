#!/usr/bin/env python3
"""Verify Megabus--3.

My Philadelphia-to-Washington plans have moved to October 10th. Sign in as Bob Chen (bob.c@test.com / TestPass123!), compare that afternoon's departures, and move booking M2V6YH from October 6th to the cheapest afternoon option on October 10th. Tell me how many afternoon options there were, the new departure time, and the amendment fee, fare difference and revised booking total.
"""
from verify_lib import (booking_by_reference, booking_journeys_of, check_only_tables_changed,
                        check_signed_in_as, check_trajectory_identity, check_visited_path,
                        contains_amount, contains_any, contains_time, final_answer, journey_of,
                        navigated_journeys, navigated_to_path, run_verifier)

TASK_ID = "Megabus--3"
REF = "M2V6YH"
NEW_DEP = "17:15"
FARE_DELTA = 0.00
AMENDMENT_FEE = 7.50
NEW_TOTAL = 75.45
OLD_TOTAL = 67.95
PHL_ID, WDC_ID = 127, 142


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_signed_in_as(judge, traj, "bob.c@test.com")
    # navigation gate: the 10-10 PHL->WDC schedule was checked before changing
    judge.check("visited_1010_schedule",
                navigated_journeys(traj, PHL_ID, WDC_ID, "2026-10-10"),
                "required: journeys PHL->WDC on 2026-10-10 (afternoon count pre-check)")
    judge.check("visited_manage_booking", navigated_to_path(traj, "/journey-planner/manage-booking"),
                "required_path=/journey-planner/manage-booking")
    check_visited_path(judge, traj, "visited_change_page", "/journey-planner/manage-booking/change")
    # answer: afternoon count + new departure time + amendment fee + fare difference + new total
    judge.check("answer_afternoon_count",
                contains_any(answer, ["1 afternoon", "one afternoon", "afternoon departure: 1",
                                      "only 1", "only one"]),
                "expected exactly one afternoon departure on 2026-10-10")
    judge.check("answer_new_departure", contains_time(answer, NEW_DEP),
                f"expected new departure {NEW_DEP} (5:15pm)")
    judge.check("answer_amendment_fee", contains_amount(answer, AMENDMENT_FEE),
                f"expected amendment fee ${AMENDMENT_FEE}")
    judge.check("answer_fare_difference", contains_amount(answer, FARE_DELTA),
                f"expected fare difference $0.00 (same 31.98 fare x 2 travelers)")
    judge.check("answer_new_total", contains_amount(answer, NEW_TOTAL),
                f"expected the booking's new total ${NEW_TOTAL} (67.95 + 0.00 + 7.50)")
    # DB after-state: M2V6YH journey moved to the 10-10 17:15 departure; total updated
    b = booking_by_reference(after_db, REF)
    judge.check("booking_present", b is not None, f"reference={REF}")
    if b:
        judge.check("booking_total_updated", abs(b["total"] - NEW_TOTAL) < 0.011,
                    f"total={b['total']!r}, expected {NEW_TOTAL} (67.95 + 0.00 + 7.50)")
        bjs = booking_journeys_of(after_db, b["id"])
        judge.check("booking_journey_moved", len(bjs) == 1, f"booking_journeys={bjs!r}")
        if bjs:
            j = journey_of(after_db, bjs[0]["journey_id"])
            judge.check("moved_to_afternoon_1010",
                        j is not None and j["origin_city_id"] == PHL_ID and j["dest_city_id"] == WDC_ID
                        and j["departure_date"] == "2026-10-10" and j["dep_time"] == NEW_DEP,
                       f"journey=({j['departure_date'] if j else None}, {j['dep_time'] if j else None})")
    check_only_tables_changed(judge, initial_db, after_db, ("bookings", "booking_journeys"))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
