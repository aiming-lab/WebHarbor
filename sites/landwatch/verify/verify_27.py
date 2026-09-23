#!/usr/bin/env python3
"""Verify LandWatch--27 — New account registration + My LandWatch empty states.

Ground truth: registering new.landbuyer@test.com / LandBuyer2026! lands on
My LandWatch ('My LandWatch' heading) with the Favorites empty state 'You
haven't saved any properties yet. Tap the heart icon on any listing to save
it here.' and the Saved Searches empty state 'No saved searches yet. Use the
Save Search button on any search results page.'; exactly one users row with
the frozen password hash is added.
"""

from verify_lib import (Judge, REGISTERED_EMAIL, REGISTERED_PASSWORD_HASH,
                        check_only_tables_changed, check_trajectory_identity,
                        check_visited_path, contains_phrase, entered_identity,
                        final_answer, run_verifier, table_delta)

TASK_ID = "LandWatch--27"


def run_checks(judge, traj, initial_db, after_db):
    answer = final_answer(traj)
    check_trajectory_identity(judge, traj, TASK_ID)
    judge.check("visited_register_page", any("/register" in u for u in
                [s.get("url", "") for s in traj.get("steps", []) if isinstance(s, dict)]),
                "expected the registration page")
    judge.check("entered_registration_identity",
                entered_identity(traj, REGISTERED_EMAIL),
                f"expected {REGISTERED_EMAIL!r} in an input step")
    check_visited_path(judge, traj, "visited_account_page", "/account")
    check_only_tables_changed(judge, initial_db, after_db, {"sessions", "users"})
    delta = table_delta(initial_db, after_db, "users")
    judge.check("exactly_one_user_added",
                delta["removed"] == [] and len(delta["added"]) == 1 and len(delta["changed"]) == 0,
                f"users delta={delta!r}")
    if delta["added"]:
        row = delta["added"][0]
        # row: id, email, password_hash, name, phone, created_at, is_benchmark
        judge.check("registered_email", row[1] == REGISTERED_EMAIL,
                    f"expected {REGISTERED_EMAIL!r}, observed {row[1]!r}")
        judge.check("registered_password_hash", row[2] == REGISTERED_PASSWORD_HASH,
                    "expected the frozen hash of LandBuyer2026!")
        judge.check("registered_not_benchmark_flag", row[6] in (0, None),
                    f"expected is_benchmark false, observed {row[6]!r}")
    judge.check("answer_heading", contains_phrase(answer, "My LandWatch"),
                "expected the 'My LandWatch' heading")
    judge.check("answer_favorites_empty_state",
                contains_phrase(answer, "haven't saved any properties") and
                contains_phrase(answer, "heart icon"),
                "expected the Favorites empty-state text")
    judge.check("answer_searches_empty_state",
                contains_phrase(answer, "No saved searches yet") and
                contains_phrase(answer, "Save Search button"),
                "expected the Saved Searches empty-state text")


if __name__ == "__main__":
    run_verifier(TASK_ID, run_checks)
