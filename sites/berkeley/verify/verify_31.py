#!/usr/bin/env python3
"""Verify UC Berkeley--31: bob saves two centres in order, then removes the first.

Stateful, with a row-id proof: the bookmarks table starts empty, so the two
inserts take ids 1 and 2; deleting the id-1 row leaves the id-2 row behind.
Requiring the surviving row's id to be exactly 2 therefore proves that both
inserts happened and that the first was deleted. A run that skips the removal
(two rows added), removes the wrong one, or adds only the second centre fails.
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
    contains_acronym,
    contains_person,
    contains_phrase,
    detail_path,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    resolve_snapshots,
    title_tokens_matched,
    user_id_for_email,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--31"
EMAIL = "bob@berkeley.edu"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 31)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    first, second = facts["first"], facts["second"]

    check_signed_in_as(judge, trajectory, EMAIL)
    check_paths_in_order(
        judge, trajectory, "workflow_in_order",
        [
            ("/login", {}),
            (detail_path("research", first["slug"]), {}),
            (detail_path("research", second["slug"]), {}),
            ("/account", {}),
            ("/account", {}),
        ],
    )
    judge.check(
        "answer_has_remaining_centre",
        contains_phrase(answer, second["name"]),
        f"expected_centre={second['name']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_remaining_director",
        contains_person(answer, second["director"]),
        f"expected_director={second['director']!r}, answer={answer!r}",
    )
    removed_named = title_tokens_matched(answer, first["name"]) >= 3 or contains_acronym(answer, first["name"])
    judge.check(
        "answer_confirms_removal",
        contains_phrase(answer, "removed") and removed_named,
        f"expected_removed_centre_tokens={title_tokens_matched(answer, first['name'])!r} "
        f"or acronym={'yes' if contains_acronym(answer, first['name']) else 'no'}; "
        f"centre={first['name']!r}; answer={answer!r}",
    )

    user_id = user_id_for_email(initial_db, EMAIL)
    if user_id is None:
        judge.check("benchmark_user_present", False, f"missing benchmark user {EMAIL!r}")
    else:
        judge.check("benchmark_user_present", True, f"user_id={user_id}")
        check_bookmarks_delta(
            judge, initial_db, after_db,
            user_id=user_id,
            added=[(user_id, "research", second["id"])],
            surviving_ids=[2],
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
