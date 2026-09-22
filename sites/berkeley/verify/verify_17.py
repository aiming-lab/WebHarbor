#!/usr/bin/env python3
"""Verify UC Berkeley--17: the three About-page statistics.

The values (and the "more than N Nobel Prizes" distractor) are derived from
tracked source; the verifier fails closed if either literal moves. The
distractor check is clause-local — quoting the alumni line elsewhere is not a
wrong answer, claiming it as the faculty count is.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_path,
    contains_count,
    contains_count_as,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    normalize_text,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--17"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 17)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_visited_path(judge, trajectory, "visited_about_page", "/about")
    for name, key in (
        ("answer_has_nobel_laureates", "nobel_laureates"),
        ("answer_has_varsity_sports", "varsity_sports"),
        ("answer_has_national_titles", "national_titles"),
    ):
        judge.check(
            name,
            contains_count(answer, facts[key]),
            f"expected_{key}={facts[key]!r}, answer={answer!r}",
        )
    faculty_clauses = [
        clause for clause in re.split(r"[.!?;\n]+", normalize_text(answer))
        if re.search(r"\blaureates?\b", clause)
    ]
    distractor = facts["distractor_nobel_prizes"]
    misquoted = [
        clause for clause in faculty_clauses
        if contains_count_as(clause, distractor, "laureates")
        or contains_count_as(clause, distractor, "laureate")
    ]
    judge.check(
        "answer_rejects_distractor_nobel_count",
        not misquoted,
        f"distractor={distractor!r}, laureate_clauses={faculty_clauses!r}; answer={answer!r}",
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
