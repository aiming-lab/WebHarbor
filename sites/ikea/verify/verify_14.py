#!/usr/bin/env python3
"""Verify IKEA--14: report Carol's most recent order number IK-240055."""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    normalize_text,
    parse_args,
)


TASK_ID = "IKEA--14"


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    normalized = normalize_text(answer)
    has_order_number = bool(
        re.search(r"(?<![a-z0-9])ik\s*[-–—]\s*240055(?!\d)", normalized)
    )
    judge = Judge(TASK_ID)
    judge.check(
        "visited_carol_orders_page",
        navigated_to_path(trajectory, "/account/orders"),
        "required_path=/account/orders",
    )
    judge.check(
        "answer_has_most_recent_order_number",
        has_order_number,
        f"expected=IK-240055, final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
