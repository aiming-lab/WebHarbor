#!/usr/bin/env python3
"""Verify AccuWeather--18: Register Jamie Lee (jamie.lee@example.test / Weather123!) and save Atlanta (stateful).

Deterministic only (no LLM calls). Ground truth is hardcoded below and never
appears in tasks.jsonl. Order: package identity -> navigation gates -> answer
facts -> SQLite snapshot contract.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    AQ_LABEL, HIGH_LABEL, HUMIDITY_LABEL, LOW_LABEL, PRECIP_LABEL, PRESSURE_LABEL, REALFEEL_LABEL,
    TEMP_LABEL, VISIBILITY_LABEL, WIND_LABEL, Judge, alert_rows, check_paths_in_order, check_read_only,
    check_saved_delta, check_search_surfaces, check_signed_in_as, check_tables_unchanged,
    check_trajectory_identity, check_visited_path, city_label, contains_all, contains_any,
    contains_clock_time, contains_condition, contains_day_label, contains_fact, fail_closed,
    final_answer, load_run, mentions, names_winner, new_users, normalize_text, parse_args,
    password_matches, resolve_snapshots, rows_unchanged_except, saved_pairs, search_queries,
    table_rows, typed_emails, user_by_email,
)

TASK_ID = "AccuWeather--18"

NEW_EMAIL = "jamie.lee@example.test"


def run_checks(judge, t, initial_db, after_db):
    check_trajectory_identity(judge, t, TASK_ID)
    a = final_answer(t)
    judge.check("visited_register_page", check_visited_path(judge, t, "visited_register", "/register"), "required_path=/register")
    judge.check("entered_new_account_email", normalize_text(NEW_EMAIL) in typed_emails(t), f"typed_emails={typed_emails(t)!r}")
    check_paths_in_order(judge, t, "register_then_atlanta_then_account", ["/register", "/weather/atlanta-ga", "/account"])
    fresh = new_users(initial_db, after_db)
    judge.check("exactly_one_new_user", len(fresh) == 1, f"new_users={[u['email'] for u in fresh]}")
    u = fresh[0] if len(fresh) == 1 else None
    judge.check("new_user_email", bool(u) and normalize_text(u["email"]) == NEW_EMAIL, f"observed={u and u['email']!r}")
    judge.check("new_user_name", bool(u) and normalize_text(u["name"]) == "jamie lee", f"observed={u and u['name']!r}")
    judge.check("new_user_password_verifies", bool(u) and password_matches(u["password_hash"], "Weather123!"), "werkzeug hash checked with hashlib")
    judge.check("seeded_users_unchanged", rows_unchanged_except(initial_db, after_db, "user", [u["id"]] if u else []), "seeded user rows identical")
    before, after = saved_pairs(initial_db), saved_pairs(after_db)
    judge.check("saved_rows_added", (after - before) == {(NEW_EMAIL, "atlanta-ga")}, f"observed_added={sorted(after - before)}")
    judge.check("saved_rows_removed", (before - after) == set(), f"observed_removed={sorted(before - after)}")
    check_tables_unchanged(judge, initial_db, after_db, ("alert",))
    judge.check("answer_mentions_atlanta", mentions(a, ["atlanta"]), f"answer={a!r}")


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID, args.no_llm)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
