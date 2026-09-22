#!/usr/bin/env python3
"""Verify UC Berkeley--23: BIDS focus areas, director and its related centres.

The related-centre names are the three rows the page's unordered ``LIMIT 3``
query actually renders (app.py:469-472); naming a same-college centre that the
page does not list fails.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_detail,
    contains_person,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    mentions,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--23"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 23)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_visited_detail(judge, trajectory, "research", facts["centre"]["slug"])
    judge.check(
        "answer_has_director",
        contains_person(answer, facts["centre"]["director"]),
        f"expected_director={facts['centre']['director']!r}, answer={answer!r}",
    )
    focus = mentions(answer, facts["focus_areas"])
    judge.check(
        "answer_has_focus_areas",
        len(focus) >= 3,
        f"expected_focus_areas={facts['focus_areas']!r}, matched={sorted(focus)!r}; answer={answer!r}",
    )
    related = mentions(answer, facts["related_names"])
    judge.check(
        "answer_names_rendered_related_centre",
        bool(related),
        f"rendered_related_centres={facts['related_names']!r}, matched={sorted(related)!r}; answer={answer!r}",
    )
    check_read_only(judge, initial_db, after_db)


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
