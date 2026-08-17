#!/usr/bin/env python3
"""Verify IKEA--12: report the support article's help category as Pickup."""
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


TASK_ID = "IKEA--12"


def identifies_pickup_category(answer: str) -> bool:
    normalized = normalize_text(answer).strip(" .!?:;,-")
    if normalized == "pickup":
        return True
    patterns = (
        r"\b(?:help\s+|article\s+)?category(?:\s+shown)?\s*(?:is|=|:|[-–—])\s*(?:the\s+)?pickup\b",
        r"\b(?:under|in)\s+(?:the\s+)?pickup(?:\s+(?:help\s+|article\s+)?category)?\b",
        r"\bpickup\s+(?:help\s+|article\s+)?category\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))

    answer = final_answer(trajectory)
    judge = Judge(TASK_ID)
    judge.check(
        "visited_pickup_readiness_article",
        navigated_to_path(trajectory, "/support/pickup-readiness-notifications"),
        "required_path=/support/pickup-readiness-notifications",
    )
    judge.check(
        "answer_identifies_pickup_category",
        identifies_pickup_category(answer),
        f"expected_category=Pickup, final_answer={answer!r}",
    )
    judge.emit()


if __name__ == "__main__":
    main()
