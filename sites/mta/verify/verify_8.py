#!/usr/bin/env python3
"""Verify MTA--8.

Log in as carol.d@test.com and book an Access-A-Ride trip from 120-55 Queens
Blvd, Kew Gardens to Elmhurst Hospital, 79-01 Broadway, Elmhurst, on Tuesday,
September 29 at 9:15 a.m., for a medical appointment, traveling with a
walker; confirm the booking reference and status in her trip list.

Frozen ground truth (seed DB): the booking creates the first AAR trip after
a clean reset: AAR-26096609 (deterministic next_ref on the pinned day) with
status "Scheduled" in carol's trip list.
"""
from verify_lib import (FIRST_AAR_REF, added_rows, check_only_tables_changed,
                        check_seed_contract, check_trajectory_identity, contains_phrase,
                        contains_ref, final_answer, navigated_to_path, run_verifier)

TASK_ID = "MTA--8"
EMAIL = "carol.d@test.com"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    check_seed_contract(judge, initial_db)
    judge.check("visited_login", navigated_to_path(traj, "/account/login"),
                "required: /account/login")
    judge.check("visited_aar_booking", navigated_to_path(traj, "/accessibility/access-a-ride/book"),
                "required: /accessibility/access-a-ride/book")
    judge.check("visited_aar_trip_list", navigated_to_path(traj, "/account/aar"),
                "required: /account/aar (trip list confirmation)")
    judge.check("answer_booking_ref", contains_ref(answer, FIRST_AAR_REF),
                f"the booking reference is {FIRST_AAR_REF}")
    judge.check("answer_status_scheduled", contains_phrase(answer, "scheduled"),
                "status in the trip list: Scheduled")
    added = added_rows(after_db, initial_db, "aar_trips", "trip_ref")
    judge.check("one_trip_added", len(added) == 1, f"added trips={[r['trip_ref'] for r in added]!r}")
    if added:
        t = added[0]
        judge.check("added_trip_ref", t["trip_ref"] == FIRST_AAR_REF,
                    f"trip_ref={t['trip_ref']!r}, expected {FIRST_AAR_REF}")
        judge.check("added_trip_pickup", "queens blvd" in (t["pickup_address"] or "").lower()
                    and "120-55" in (t["pickup_address"] or ""),
                    f"pickup={t['pickup_address']!r}")
        judge.check("added_trip_destination", "elmhurst hospital" in (t["destination_address"] or "").lower(),
                    f"destination={t['destination_address']!r}")
        judge.check("added_trip_date", t["trip_date"] == "2026-09-29", f"date={t['trip_date']!r}")
        judge.check("added_trip_time", (t["pickup_time"] or "").startswith("09:15"),
                    f"time={t['pickup_time']!r}")
        judge.check("added_trip_walker", (t["mobility_aid"] or "") == "Walker",
                    f"mobility_aid={t['mobility_aid']!r}")
        judge.check("added_trip_purpose", "medical" in (t["purpose"] or "").lower(),
                    f"purpose={t['purpose']!r}")
        judge.check("added_trip_status", t["status"] == "Scheduled", f"status={t['status']!r}")
    if added:
        judge.check("one_passenger", added[0]["passengers"] == 1, "Carol travels alone")
        judge.check("destination_street", "79-01" in added[0]["destination_address"] and "broadway" in added[0]["destination_address"].lower(), "Hospital address must match")
    check_only_tables_changed(judge, initial_db, after_db, ("aar_trips",))


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
