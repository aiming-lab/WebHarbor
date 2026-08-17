#!/usr/bin/env python3
"""Verify IKEA--1: report LACK's $49.99 price and absence of a Local deal."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    contains_money,
    explicitly_denies_label,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
)


TASK_ID = "IKEA--1"


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    judge = Judge(TASK_ID)
    judge.check(
        "visited_lack_product_page",
        navigated_to_path(trajectory, "/product/IK-10002"),
        "required_path=/product/IK-10002",
    )
    judge.check(
        "answer_has_current_price",
        contains_money(answer, 49, 99),
        f"expected=$49.99, final_answer={answer!r}",
    )
    judge.check(
        "answer_says_not_local_deal",
        explicitly_denies_label(answer, "local deal"),
        f"final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
