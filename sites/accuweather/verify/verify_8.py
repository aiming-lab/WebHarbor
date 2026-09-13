#!/usr/bin/env python3
"""Verify AccuWeather--8: Sign in as bob.smith@test.com and enable exactly Severe weather + Rain starting soon for Chicago (stateful).

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

TASK_ID = "AccuWeather--8"

EXPECTED_ALERTS = {("bob.smith@test.com", "chicago-il", "severe", 1), ("bob.smith@test.com", "chicago-il", "rain", 1)}


def run_checks(judge, t, initial_db, after_db):
    check_trajectory_identity(judge, t, TASK_ID)
    check_signed_in_as(judge, t, "bob.smith@test.com")
    check_paths_in_order(judge, t, "login_then_chicago_alerts", ["/login", "/alerts/chicago-il"])
    before, after = alert_rows(initial_db), alert_rows(after_db)
    judge.check("alerts_initially_empty", before == set(), f"initial_alerts={sorted(before)}")
    judge.check("alerts_exactly_severe_and_rain_for_chicago", after == EXPECTED_ALERTS, f"expected={sorted(EXPECTED_ALERTS)}, observed={sorted(after)}")
    check_tables_unchanged(judge, initial_db, after_db, ("user", "saved_location"))


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
