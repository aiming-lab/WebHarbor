#!/usr/bin/env python3
"""Verify UC Berkeley--7: an EECS professor who works on artificial intelligence.

The accepted set is derived from the department roster with an AI-family rule
over ``research_interests`` (the literal phrase "artificial intelligence" matches
one row; the allowlist is the rule the task text implies). The answer must bind
to one named row: the profile must have been opened and the reported interests
must be that row's.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    contains_person,
    detail_visited,
    fail_closed,
    final_answer,
    interest_token_matches,
    Judge,
    load_run,
    navigated_to_path,
    params_visited,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--7"
AI_QUERY_RE = re.compile(r"(artificial|machine learning|deep learning|reinforcement|robot|ai\b)")


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 7)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    route_ok = (
        params_visited(trajectory, "/faculty", dept=facts["department"]["slug"])
        or params_visited(trajectory, "/faculty", q=AI_QUERY_RE)
        or navigated_to_path(trajectory, f"/departments/{facts['department']['slug']}")
    )
    judge.check(
        "visited_eecs_faculty_route",
        route_ok,
        "required: /faculty?dept=eecs, an AI-keyword /faculty search, or the EECS department page",
    )

    named = [row for row in facts["allowed"] if contains_person(answer, row["name"])]
    judge.check(
        "named_eecs_ai_professor",
        bool(named),
        f"allowed={[row['name'] for row in facts['allowed']]!r}, answer={answer!r}",
    )
    visited = [row for row in named if detail_visited(trajectory, "faculty", row["slug"])]
    judge.check(
        "visited_named_professor_profile",
        bool(visited),
        f"named={[row['slug'] for row in named]!r}, observed={[row['slug'] for row in facts['members'] if detail_visited(trajectory, 'faculty', row['slug'])]!r}",
    )
    bound = [
        row for row in visited
        if interest_token_matches(answer, row["research_interests"]) >= 2
    ]
    judge.check(
        "answer_interests_bind_to_profile",
        bool(bound),
        f"named={[row['name'] for row in named]!r}, "
        f"interest_token_hits={[interest_token_matches(answer, row['research_interests']) for row in visited]!r}; "
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
