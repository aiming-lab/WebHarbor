#!/usr/bin/env python3
"""Verify IKEA--14: report Carol's most recent order number IK-240055."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_signed_in_as,
    check_trajectory_identity,
    extract_order_numbers,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
)


TASK_ID = "IKEA--14"
EMAIL = "carol.d@test.com"
EXPECTED_ORDER = "IK-240055"


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    reported_orders = extract_order_numbers(answer)
    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    check_signed_in_as(judge, trajectory, EMAIL)
    judge.check(
        "visited_carol_orders_page",
        navigated_to_path(trajectory, "/account/orders"),
        "required_path=/account/orders",
    )
    judge.check(
        "answer_has_most_recent_order_number",
        reported_orders == {EXPECTED_ORDER},
        f"expected={EXPECTED_ORDER}, reported_orders={sorted(reported_orders)!r}, final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
