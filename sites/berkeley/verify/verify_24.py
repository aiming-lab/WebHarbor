#!/usr/bin/env python3
"""Verify UC Berkeley--24: the Economics PhD -> department -> faculty walk.

Three hops, each gated in order; each answer fact binds to the page it came from
(chair and programme list to the department page, interests to a member profile).
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_paths_in_order,
    check_read_only,
    check_trajectory_identity,
    contains_degree_type,
    contains_person,
    detail_path,
    fail_closed,
    final_answer,
    interest_token_matches,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--24"
FACULTY_PATH_RE = re.compile(r"/faculty/[a-z0-9-]+")


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 24)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    check_paths_in_order(
        judge, trajectory, "workflow_in_order",
        [
            (detail_path("program", facts["program"]["slug"]), {}),
            (detail_path("department", facts["department"]["slug"]), {}),
            (FACULTY_PATH_RE, {}),
        ],
    )
    judge.check(
        "answer_has_chair",
        contains_person(answer, facts["chair"]),
        f"expected_chair={facts['chair']!r}, answer={answer!r}",
    )
    degree_types = sorted({row["degree_type"] for row in facts["programmes"]})
    missing = [value for value in degree_types if not contains_degree_type(answer, value)]
    judge.check(
        "answer_has_department_programmes",
        not missing,
        f"expected_degree_types={degree_types!r}, missing={missing!r}; answer={answer!r}",
    )
    bound = [
        member for member in facts["members"]
        if contains_person(answer, member["name"])
        and interest_token_matches(answer, member["research_interests"]) >= 2
    ]
    judge.check(
        "answer_has_economics_faculty_interests",
        bool(bound),
        f"members={[row['name'] for row in facts['members']]!r}, "
        f"interest_token_hits={[interest_token_matches(answer, row['research_interests']) for row in facts['members']]!r}; "
        f"answer={answer!r}",
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
