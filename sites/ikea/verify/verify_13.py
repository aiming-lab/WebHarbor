#!/usr/bin/env python3
"""Verify IKEA--13: report any service listed on IKEA Atlanta's detail page."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    contains_any,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    parse_args,
)


TASK_ID = "IKEA--13"
ATLANTA_SERVICES = ("Assembly planning", "Kitchen consultation", "Returns desk")


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    judge = Judge(TASK_ID)
    judge.check(
        "visited_atlanta_store_page",
        navigated_to_path(trajectory, "/stores/atlanta-ga"),
        "required_path=/stores/atlanta-ga",
    )
    judge.check(
        "answer_has_atlanta_service",
        contains_any(answer, ATLANTA_SERVICES),
        f"accepted={ATLANTA_SERVICES!r}, final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
