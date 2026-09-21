#!/usr/bin/env python3
"""Verify UC Berkeley--16: the single online degree programme.

``q=online`` finds nothing (the word is not in any programme name or
description), so the only route is scanning the listings for the online badge;
the detail visit pins the programme and its school. Naming any other catalog
programme near "online" fails.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    affirmative_near,
    check_read_only,
    check_trajectory_identity,
    check_visited_detail,
    check_visited_path,
    contains_degree_type,
    contains_phrase,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
    title_tokens,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--16"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 16)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    programme = facts["program"]

    check_visited_path(judge, trajectory, "visited_programme_listing", "/programs")
    check_visited_detail(judge, trajectory, "program", programme["slug"])
    judge.check(
        "answer_has_programme",
        contains_phrase(answer, programme["name"]),
        f"expected_programme={programme['name']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_degree_type",
        contains_degree_type(answer, programme["degree_type"]),
        f"expected_degree_type={programme['degree_type']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_school",
        contains_phrase(answer, programme["college_name"]),
        f"expected_school={programme['college_name']!r}, answer={answer!r}",
    )
    other_online = [
        name for name in facts["others"]
        if len(title_tokens(name)) >= 2 and affirmative_near(answer, name, "online", 80)
    ]
    judge.check(
        "answer_no_other_online_programmes",
        not other_online,
        f"other_programmes_reported_online={other_online!r}; answer={answer!r}",
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
