#!/usr/bin/env python3
"""Verify UC Berkeley--30: alice saves a named research centre to her bookmarks.

Stateful. The gate is the ordered workflow (sign-in, centre page, My Account)
and the binding check is the exact bookmark row delta against the initial
snapshot — a run that claims the save without writing it fails on the delta.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_bookmarks_delta,
    check_paths_in_order,
    check_signed_in_as,
    check_tables_unchanged,
    check_trajectory_identity,
    contains_any,
    contains_person,
    contains_phrase,
    detail_path,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
    user_id_for_email,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--30"
EMAIL = "alice@berkeley.edu"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 30)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    centre = facts["centre"]

    check_signed_in_as(judge, trajectory, EMAIL)
    check_paths_in_order(
        judge, trajectory, "workflow_in_order",
        [
            ("/login", {}),
            (detail_path("research", centre["slug"]), {}),
            ("/account", {}),
        ],
    )
    judge.check(
        "answer_has_centre",
        contains_phrase(answer, centre["name"]),
        f"expected_centre={centre['name']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_director",
        contains_person(answer, facts["director"]),
        f"expected_director={facts['director']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_confirms_saved",
        contains_any(answer, ("saved", "listed", "bookmarks", "my account")),
        f"answer={answer!r}",
    )

    user_id = user_id_for_email(initial_db, EMAIL)
    if user_id is None:
        judge.check("benchmark_user_present", False, f"missing benchmark user {EMAIL!r}")
    else:
        judge.check("benchmark_user_present", True, f"user_id={user_id}")
        check_bookmarks_delta(
            judge, initial_db, after_db,
            user_id=user_id,
            added=[(user_id, "research", centre["id"])],
        )
    check_tables_unchanged(judge, initial_db, after_db, ("users",), prefix="read_only_")


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
