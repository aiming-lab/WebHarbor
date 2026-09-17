#!/usr/bin/env python3
"""Verify UC Berkeley--28: how many programmes require the GRE, and which degree type.

No GRE filter exists, so the badge is only visible by scanning the programme
listings: the gate accepts the two degree-filtered listings (which cover every
badged row) or four distinct pages of the full listing. The count and the modal
degree type are derived from the snapshot.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    contains_count,
    contains_degree_type,
    fail_closed,
    final_answer,
    Judge,
    listing_pages_visited,
    load_run,
    params_visited,
    parse_args,
    resolve_snapshots,
)
from ground_truth import task_ground_truth  # noqa: E402


TASK_ID = "UC Berkeley--28"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    facts = task_ground_truth(initial_db, 28)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)

    pages = listing_pages_visited(trajectory, "/programs")
    both_filters = (
        params_visited(trajectory, "/programs", degree="PhD")
        and params_visited(trajectory, "/programs", degree="MS")
    )
    judge.check(
        "visited_gre_programme_listings",
        both_filters or len(pages) >= 4,
        f"degree_filtered_listings={both_filters}, distinct_unfiltered_or_filtered_pages={len(pages)}; "
        f"observed={pages!r}",
    )
    judge.check(
        "answer_has_gre_count",
        contains_count(answer, facts["count"]),
        f"expected_count={facts['count']!r}, answer={answer!r}",
    )
    judge.check(
        "answer_has_modal_degree_type",
        contains_degree_type(answer, facts["most_common_degree"]),
        f"expected_degree_type={facts['most_common_degree']!r}, by_degree={facts['by_degree']!r}; "
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
