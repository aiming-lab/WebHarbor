#!/usr/bin/env python3
"""Verify IKEA--9: report Alice's newest reward label."""
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
)


TASK_ID = "IKEA--9"


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    judge = Judge(TASK_ID)
    judge.check(
        "visited_alice_rewards_page",
        navigated_to_path(trajectory, "/account/rewards"),
        "required_path=/account/rewards",
    )
    judge.check(
        "answer_has_newest_reward_label",
        contains_all(answer, ["Bedroom storage order"]),
        f"final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
