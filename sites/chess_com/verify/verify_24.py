#!/usr/bin/env python3
"""Verify carol sets her location to Berlin, Germany in Chess.com--24."""


from verify_lib import (Judge, check_read_only, check_signed_in_as, check_trajectory_identity,
                        check_visited_path, contains_amount, contains_any, contains_count, contains_date,
                        contains_percent, contains_phrase, db_query, final_answer, navigated_to_path,
                        phrases_in_order, run_verifier, table_delta)

TASK_ID = "Chess.com--24"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    # Navigation gates: login and the settings page.
    check_signed_in_as(judge, traj, "carol.d@test.com", "carol_d")
    check_visited_path(judge, traj, "visited_settings", "/settings")
    # Frozen ground truth: the settings page shows the location text 'Berlin, Germany'.
    judge.check("answer_location", contains_phrase(answer, "Berlin, Germany"),
                "expected 'Berlin, Germany'")
    # DB after-state: exactly the carol_d user row changed, only in the location column
    # (seed 'London' -> 'Berlin, Germany'); every other user row is identical.
    from verify_lib import check_only_tables_changed
    delta = table_delta(initial_db, after_db, "users")
    changed_ok = len(delta["changed"]) == 1 and delta["changed"][0][0][0] == 1178
    if changed_ok:
        before_row, after_row = delta["changed"][0]
        cols = __import__("verify_lib").table_columns(after_db, "users")
        diffs = [c for c, (b, a) in zip(cols, zip(before_row, after_row)) if b != a]
        # R10 fix: the settings route now stores `.strip() or None`, so a NULL
        # about stays NULL on profile saves — exactly one column may differ.
        changed_ok = diffs == ["location"] and after_row[cols.index("location")] == "Berlin, Germany"
    judge.check("carol_location_exact_delta",
                changed_ok and not delta["added"] and not delta["removed"],
                f"delta={delta!r} (expected row 1178 changed only in location -> 'Berlin, Germany')")
    check_only_tables_changed(judge, initial_db, after_db, {"users"})



if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
