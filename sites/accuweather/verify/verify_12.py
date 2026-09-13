#!/usr/bin/env python3
"""Verify AccuWeather--12: Los Angeles vs San Francisco air-quality comparison (read-only).

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

TASK_ID = "AccuWeather--12"

def run_checks(judge, t, initial_db, after_db):
    check_trajectory_identity(judge, t, TASK_ID)
    a = final_answer(t)
    check_search_surfaces(judge, t, "los-angeles-ca")
    check_search_surfaces(judge, t, "san-francisco-ca")
    check_visited_path(judge, t, "visited_air_quality_los_angeles", "/air-quality/los-angeles-ca")
    check_visited_path(judge, t, "visited_air_quality_san_francisco", "/air-quality/san-francisco-ca")
    judge.check("answer_los_angeles_value", contains_fact(a, 41, label=city_label("los angeles", "la", "l.a.")), f"expected LA 41, answer={a!r}")
    judge.check("answer_san_francisco_value", contains_fact(a, 18, label=city_label("san francisco", "sf")), f"expected SF 18, answer={a!r}")
    judge.check("answer_names_better_city", names_winner(a, ["san francisco", "sf"], ["los angeles", "la", "l.a."], ["better", "lower", "cleaner", "best", "lowest", "healthier"], ["worse", "higher", "worst", "highest", "poorer"]), f"expected San Francisco better, answer={a!r}")
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
