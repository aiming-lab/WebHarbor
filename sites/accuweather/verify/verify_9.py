#!/usr/bin/env python3
"""Verify AccuWeather--9: Sign in as carol.w@test.com, switch to Celsius, report New York temperature and RealFeel in Celsius (stateful).

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

TASK_ID = "AccuWeather--9"

def run_checks(judge, t, initial_db, after_db):
    check_trajectory_identity(judge, t, TASK_ID)
    a = final_answer(t)
    check_signed_in_as(judge, t, "carol.w@test.com")
    check_paths_in_order(judge, t, "login_then_settings_then_new_york", ["/login", "/settings", "/weather/new-york-ny"])
    before, after = user_by_email(initial_db, "carol.w@test.com"), user_by_email(after_db, "carol.w@test.com")
    judge.check("carol_unit_is_celsius", bool(after) and after["unit"] == "C", f"before_unit={before and before['unit']!r}, after_unit={after and after['unit']!r}")
    judge.check("carol_other_columns_unchanged", bool(before and after) and {k: v for k, v in before.items() if k != "unit"} == {k: v for k, v in after.items() if k != "unit"}, "email/name/password_hash identical")
    judge.check("other_users_unchanged", bool(before) and rows_unchanged_except(initial_db, after_db, "user", [before["id"]]), "user rows other than carol identical")
    check_tables_unchanged(judge, initial_db, after_db, ("saved_location", "alert"))
    judge.check("answer_temperature_celsius", contains_fact(a, 26, unit="temp", label=TEMP_LABEL), f"expected 26, answer={a!r}")
    judge.check("answer_realfeel_celsius", contains_fact(a, 28, unit="temp", label=REALFEEL_LABEL), f"expected 28, answer={a!r}")


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
