#!/usr/bin/env python3
"""Verify Amtrak--17: Alice books NYP->WAS 2026-04-20, direct option, Business fare, mock checkout; reports the new booking code (stateful).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    LOG_TABLES,
    booking_payment,
    booking_segments,
    booking_tickets,
    check_paths_in_order,
    check_signed_in_as,
    check_tables_unchanged,
    check_trajectory_identity,
    contains_code,
    db_query,
    fail_closed,
    final_answer,
    load_run,
    new_booking_rows,
    parse_args,
    resolve_snapshots,
    reward_row,
    rows_unchanged_except,
    table_delta,
    user_row,
)


TASK_ID = "Amtrak--17"
EMAIL = "alice.j@test.com"
ORIGIN = "NYP"
DESTINATION = "WAS"
DEPARTURE = "2026-04-20"
FARE_CLASS_NAME = "Business"
ACCOMMODATION = "Business Seat"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_signed_in_as(judge, trajectory, EMAIL)
    check_paths_in_order(
        judge, trajectory, "checkout_workflow_in_order",
        [("/login", {}),
         ("/booking/results", {"origin": ORIGIN, "destination": DESTINATION, "departure_date": DEPARTURE}),
         ("/booking/select-trip", {}), ("/booking/select-fare", {}), ("/booking/passengers", {}),
         ("/booking/review", {}), ("/booking/checkout", {}), ("/booking/confirmation", {})],
    )
    alice_before, alice_after = user_row(initial_db, EMAIL), user_row(after_db, EMAIL)
    new_rows = new_booking_rows(initial_db, after_db)
    judge.check("exactly_one_new_booking", len(new_rows) == 1, f"new_bookings={[r.get('booking_code') for r in new_rows]!r}")
    row = new_rows[0] if len(new_rows) == 1 else {}
    booking_id = int(row["id"]) if row else -1
    judge.check("new_booking_belongs_to_alice", bool(alice_after) and row.get("user_id") == alice_after["id"], f"row_user_id={row.get('user_id')!r}")
    judge.check("new_booking_is_nyp_to_was_0420_one_way",
                row.get("origin_code") == ORIGIN and row.get("destination_code") == DESTINATION
                and str(row.get("departure_date") or "")[:10] == DEPARTURE and row.get("trip_type") == "one-way"
                and row.get("status") == "Confirmed",
                f"origin={row.get('origin_code')!r}, destination={row.get('destination_code')!r}, departure={row.get('departure_date')!r}, type={row.get('trip_type')!r}, status={row.get('status')!r}")
    segments = booking_segments(after_db, booking_id)
    judge.check("single_direct_business_segment",
                len(segments) == 1 and segments[0]["origin_code"] == ORIGIN and segments[0]["destination_code"] == DESTINATION
                and segments[0]["fare_class_name"] == FARE_CLASS_NAME and segments[0]["accommodation_type"] == ACCOMMODATION,
                f"segments={[(s['route_name'], s['origin_code'], s['destination_code'], s['fare_class_name'], s['accommodation_type']) for s in segments]!r}")
    tickets = booking_tickets(after_db, booking_id)
    business_id = db_query(after_db, "SELECT id FROM fare_classes WHERE slug='business'")[0]["id"]
    judge.check("tickets_issued_for_business_fare",
                bool(tickets) and all(t["fare_class_id"] == business_id and t["status"] == "Issued" and t["accommodation_type"] == ACCOMMODATION for t in tickets),
                f"tickets={[(t['fare_class_id'], t['status'], t['accommodation_type']) for t in tickets]!r}")
    payment = booking_payment(after_db, booking_id)
    judge.check("mock_payment_approved_for_total",
                bool(payment) and payment["status"] == "Approved" and abs(float(payment["amount"]) - float(row.get("total_amount") or -1)) < 0.005,
                f"payment={payment!r}, total_amount={row.get('total_amount')!r}")
    reward_before, reward_after = reward_row(initial_db, EMAIL), reward_row(after_db, EMAIL)
    earned = int(row.get("reward_points_earned") or 0)
    judge.check("reward_points_credited",
                bool(reward_before) and bool(reward_after) and earned > 0
                and reward_after["points_balance"] == reward_before["points_balance"] + earned,
                f"before={reward_before and reward_before['points_balance']!r}, after={reward_after and reward_after['points_balance']!r}, earned={earned}")
    activity = table_delta(initial_db, after_db, "reward_activities")
    judge.check("one_new_reward_activity_for_booking",
                len(activity["added"]) == 1 and not activity["removed"] and not activity["changed"]
                and row.get("booking_code") in [str(v) for v in activity["added"][0]],
                f"delta={activity!r}")
    for table in ("bookings", "booking_segments", "tickets", "passengers", "payment_mocks"):
        delta = table_delta(initial_db, after_db, table)
        judge.check(f"{table}_only_added_for_new_booking",
                    not delta["removed"] and not delta["changed"]
                    and (table == "bookings" and len(delta["added"]) == 1
                         or table != "bookings" and bool(delta["added"]) and all(booking_id in [v for v in r if isinstance(v, int)] for r in delta["added"])),
                    f"delta_counts=added:{len(delta['added'])} removed:{len(delta['removed'])} changed:{len(delta['changed'])}")
    # Booking is the only write this task authorises: the funnel passes through
    # /booking/results, which must not log the search.
    check_tables_unchanged(judge, initial_db, after_db, LOG_TABLES)
    judge.check("other_users_unchanged", bool(alice_after) and rows_unchanged_except(initial_db, after_db, "users", [alice_after["id"]]), "table=users")
    judge.check("other_reward_accounts_unchanged", bool(reward_after) and rows_unchanged_except(initial_db, after_db, "reward_accounts", [reward_after["id"]]), "table=reward_accounts")
    code = str(row.get("booking_code") or "")
    judge.check("answer_has_new_booking_code", bool(code) and contains_code(answer, code), f"row_booking_code={code!r}, answer={answer!r}")


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
