#!/usr/bin/env python3
"""Verify WebMD Doctor--6: Dr. Fatima Jensen (Psychiatry, Media): oldest review date + its star rating, second review page required (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below, never in
tasks.jsonl, and cross-checked against the initial snapshot by ground_truth.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    check_read_only,
    check_trajectory_identity,
    check_visited_profile,
    contains_review_date,
    contains_star_rating,
    fail_closed,
    final_answer,
    Judge,
    load_run,
    parse_args,
    profile_visited_with,
    resolve_snapshots,
)


TASK_ID = "WebMD Doctor--6"
import datetime as _dt

SLUG = "fatima-jensen-e5a26d53"
OLDEST_DATE = _dt.date(2022, 11, 2)
OLDEST_RATING = 4


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    check_visited_profile(judge, trajectory, SLUG)
    judge.check("visited_reviews_page_2", profile_visited_with(trajectory, SLUG, rpage="2"), f"required=/doctor/{SLUG}-overview?rpage=2")
    judge.check("answer_has_oldest_review_date", contains_review_date(answer, OLDEST_DATE), f"expected={OLDEST_DATE.isoformat()!r}, answer={answer!r}")
    judge.check("answer_has_oldest_review_rating", contains_star_rating(answer, OLDEST_RATING), f"expected={OLDEST_RATING!r} stars, answer={answer!r}")
    check_read_only(judge, initial_db, after_db)


def main() -> None:
    args = parse_args()
    try:
        trajectory = load_run(args.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(args, TASK_ID)
    judge = Judge(TASK_ID)
    try:
        run_checks(judge, trajectory, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001 - any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    judge.emit()


if __name__ == "__main__":
    main()
