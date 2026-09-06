#!/usr/bin/env python3
"""Verify IKEA--4: identify 5-year home protection as the longer plan."""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_trajectory_identity,
    fail_closed,
    final_answer,
    load_run,
    navigated_to_path,
    normalize_text,
    parse_args,
)


TASK_ID = "IKEA--4"


def identifies_longer_plan(answer: str) -> bool:
    normalized = normalize_text(answer).replace("–", "-").replace("—", "-")
    has_plan = bool(
        re.search(r"\b5\s*(?:-|\s)\s*year\s+home\s+protection\b", normalized)
    )
    has_duration_comparison = bool(
        re.search(
            r"\b(?:longer|longest|lasts?\s+(?:the\s+)?longer|greater\s+duration|"
            r"more\s+years|outlasts?)\b",
            normalized,
        )
    )
    return has_plan and has_duration_comparison


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
        "visited_knapper_product_page",
        navigated_to_path(trajectory, "/product/IK-10023"),
        "required_path=/product/IK-10023",
    )
    judge.check(
        "answer_identifies_longer_plan",
        identifies_longer_plan(answer),
        f"expected=5-year home protection is longer, final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
