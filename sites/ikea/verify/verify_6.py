#!/usr/bin/env python3
"""Verify IKEA--6: report Brooklyn's Swedish Restaurant and Click & collect."""
from __future__ import annotations

import os
import re
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
    normalize_text,
    parse_args,
)


TASK_ID = "IKEA--6"


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    normalized = normalize_text(answer)
    has_restaurant = contains_all(answer, ["Swedish Restaurant"])
    has_collect = bool(re.search(r"\bclick\s*(?:&|and)\s*collect\b", normalized))
    judge = Judge(TASK_ID)
    check_trajectory_identity(judge, trajectory, TASK_ID)
    judge.check(
        "visited_brooklyn_store_page",
        navigated_to_path(trajectory, "/stores/brooklyn-ny"),
        "required_path=/stores/brooklyn-ny",
    )
    judge.check(
        "answer_has_swedish_restaurant",
        has_restaurant,
        f"final_answer={answer!r}",
    )
    judge.check(
        "answer_has_click_and_collect",
        has_collect,
        f"final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
