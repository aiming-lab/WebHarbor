#!/usr/bin/env python3
"""Verify IKEA--15: Alice newly compares IK-10010 and reports a full spec row."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    contains_all,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
    relation_count,
    resolve_db,
)


TASK_ID = "IKEA--15"
EMAIL = "alice.j@test.com"
SKU = "IK-10010"
SPEC_ROWS = (
    ("Series", "IKEA PS 2014"),
    ("Rating", "4.1"),
    ("Availability", "Ready for pickup"),
    ("IKEA product ID", "00311498"),
    ("Material", "Blade: ABS plastic, Metallized, Paint"),
    ("Size", '14"'),
    ("Care", "Dust the lamp with a dust cloth."),
)


def matching_spec_rows(answer: str) -> list[str]:
    return [
        f"{name}: {value}"
        for name, value in SPEC_ROWS
        if contains_all(answer, [name, value])
    ]


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    initial_db = resolve_db(args.initial_db, args.container, "instance_seed")
    after_db = resolve_db(args.after_db, args.container, "instance")
    if not initial_db or not after_db:
        fail_closed(
            TASK_ID,
            "database_unavailable",
            "both initial and after IKEA database snapshots are required",
        )

    answer = final_answer(trajectory)
    try:
        before_count = relation_count(initial_db, "compare_items", EMAIL, SKU)
        after_count = relation_count(after_db, "compare_items", EMAIL, SKU)
    except Exception as exc:
        fail_closed(TASK_ID, "database_query_failed", str(exc))
    matched_rows = matching_spec_rows(answer)

    judge = Judge(TASK_ID)
    judge.check(
        "visited_compare_page",
        navigated_to_path(trajectory, "/compare"),
        "required_path=/compare",
    )
    judge.check(
        "initial_compare_target_absent",
        before_count == 0,
        f"email={EMAIL}, sku={SKU}, initial_count={before_count!r}",
    )
    judge.check(
        "target_added_to_alice_compare",
        after_count is not None and after_count > 0,
        f"email={EMAIL}, sku={SKU}, after_count={after_count!r}",
    )
    judge.check(
        "answer_has_complete_spec_row",
        bool(matched_rows),
        f"matched_rows={matched_rows!r}, final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
