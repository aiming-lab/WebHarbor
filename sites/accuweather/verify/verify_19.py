#!/usr/bin/env python3
"""Verify AccuWeather--19: Phoenix vs New Orleans temperature/humidity and RealFeel heat-index comparison (read-only).

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

TASK_ID = "AccuWeather--19"

def run_checks(judge, t, initial_db, after_db):
    check_trajectory_identity(judge, t, TASK_ID)
    a = final_answer(t)
    check_search_surfaces(judge, t, "new-orleans-la")
    check_visited_path(judge, t, "visited_weather_phoenix", "/weather/phoenix-az")
    check_visited_path(judge, t, "visited_weather_new_orleans", "/weather/new-orleans-la")
    judge.check("answer_phoenix_temperature", contains_fact(a, 104, unit="temp", label=TEMP_LABEL), f"expected 104, answer={a!r}")
    judge.check("answer_phoenix_humidity", contains_fact(a, 18, unit="percent", label=HUMIDITY_LABEL, allow_bare=False), f"expected 18%, answer={a!r}")
    judge.check("answer_new_orleans_temperature", contains_fact(a, 89, unit="temp", label=TEMP_LABEL), f"expected 89, answer={a!r}")
    judge.check("answer_new_orleans_humidity", contains_fact(a, 75, unit="percent", label=HUMIDITY_LABEL, allow_bare=False), f"expected 75%, answer={a!r}")
    judge.check("answer_names_higher_heat_index_city", names_winner(a, ["phoenix"], ["new orleans", "nola"], ["higher", "hotter", "greater", "highest", "hottest", "larger"], ["lower", "cooler", "lowest", "smaller", "less"]), f"expected Phoenix higher, answer={a!r}")
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
