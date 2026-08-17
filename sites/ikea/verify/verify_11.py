#!/usr/bin/env python3
"""Verify IKEA--11: report ROSENMANDEL dimensions as 53 x 98 inches."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    contains_dimensions_inches,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
)


TASK_ID = "IKEA--11"


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    judge = Judge(TASK_ID)
    judge.check(
        "visited_rosenmandel_product_page",
        navigated_to_path(trajectory, "/product/IK-10020"),
        "required_path=/product/IK-10020",
    )
    judge.check(
        "answer_has_53_by_98_inches",
        contains_dimensions_inches(answer, 53, 98),
        f"expected=53x98 inches, final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
