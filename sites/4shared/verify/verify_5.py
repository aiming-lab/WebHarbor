#!/usr/bin/env python3
"""Deterministic verifier for 4shared--5 (read-only, comparison).

In Videos compare Open Data Mapping Basics (27:03) with City Cycling Route Planning
(19:05) by opening both detail pages; which is longer, and both runtimes.

Checks: identity | BOTH detail pages opened | answer has both runtimes and names
Open Data Mapping Basics as the longer one | every table unchanged.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_detail_visited, check_read_only, check_trajectory_identity,  # noqa: E402
                        claims_winner, contains_runtime, fail_closed, final_answer, load_run,
                        parse_args, resolve_snapshots)

TASK_ID = "4shared--5"
WINNER_SLUG, WINNER_KEY, WINNER_RUNTIME = "open-data-mapping-basics-mp4-22", "Open Data Mapping Basics", "27:03"
LOSER_SLUG, LOSER_KEY, LOSER_RUNTIME = "city-cycling-route-planning-mp4-29", "City Cycling Route Planning", "19:05"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_detail_visited(j, t, WINNER_SLUG)
    check_detail_visited(j, t, LOSER_SLUG)
    fa = final_answer(t)
    j.check("answer_has_winner_runtime", contains_runtime(fa, WINNER_RUNTIME), f"expected={WINNER_RUNTIME!r} answer={fa[:200]!r}")
    j.check("answer_has_loser_runtime", contains_runtime(fa, LOSER_RUNTIME), f"expected={LOSER_RUNTIME!r} answer={fa[:200]!r}")
    j.check("answer_names_longer_video", claims_winner(fa, WINNER_KEY, [LOSER_KEY]), f"expected_longer={WINNER_KEY!r} answer={fa[:200]!r}")
    check_read_only(j, initial_db, after_db)


def main():
    a = parse_args()
    try:
        t = load_run(a.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(a, TASK_ID)
    j = Judge(TASK_ID, a.no_llm)
    try:
        run_checks(j, t, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    j.emit()


if __name__ == "__main__":
    main()
