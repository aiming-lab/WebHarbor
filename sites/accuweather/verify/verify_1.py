#!/usr/bin/env python3
"""Verify AccuWeather--1: Portland search -> Portland, Maine condition, wind and visibility (read-only).

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

TASK_ID = "AccuWeather--1"

def run_checks(judge, t, initial_db, after_db):
    check_trajectory_identity(judge, t, TASK_ID)
    a = final_answer(t)
    check_search_surfaces(judge, t, "portland-me")
    check_visited_path(judge, t, "visited_weather_portland_me", "/weather/portland-me")
    judge.check("answer_condition", contains_condition(a, "Mostly cloudy"), f"expected 'Mostly cloudy', answer={a!r}")
    judge.check("answer_wind", contains_fact(a, 8, unit="mph", label=WIND_LABEL), f"expected 8 mph, answer={a!r}")
    judge.check("answer_visibility", contains_fact(a, 10, unit="mi", label=VISIBILITY_LABEL), f"expected 10 mi, answer={a!r}")
    check_read_only(judge, initial_db, after_db)


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
