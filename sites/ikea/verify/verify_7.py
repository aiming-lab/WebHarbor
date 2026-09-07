#!/usr/bin/env python3
"""Verify IKEA--7: report Room-of-choice delivery."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_trajectory_identity,
    contains_hyphenated_phrase,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
)


TASK_ID = "IKEA--7"


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
        "visited_large_item_delivery_article",
        navigated_to_path(trajectory, "/support/large-item-delivery"),
        "required_path=/support/large-item-delivery",
    )
    judge.check(
        "answer_has_room_of_choice_delivery",
        contains_hyphenated_phrase(answer, ["room", "of", "choice", "delivery"]),
        f"final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
