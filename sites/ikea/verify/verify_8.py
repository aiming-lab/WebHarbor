#!/usr/bin/env python3
"""Verify IKEA--8: report order IK-240001 status as Preparing order."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_trajectory_identity,
    contains_all,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
    trajectory_last_email,
)


TASK_ID = "IKEA--8"
EMAIL = "alice.j@test.com"


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    judge.check(
        "entered_order_email",
        trajectory_last_email(trajectory) == EMAIL,
        f"expected_email={EMAIL!r}, last_entered_email={trajectory_last_email(trajectory)!r}",
    )
    judge.check(
        "visited_order_lookup_page",
        navigated_to_path(trajectory, "/order-lookup"),
        "required_path=/order-lookup",
    )
    judge.check(
        "answer_has_preparing_order",
        contains_all(answer, ["Preparing order"]),
        f"final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
