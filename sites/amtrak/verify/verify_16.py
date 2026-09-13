#!/usr/bin/env python3
"""Verify Amtrak--16: Help search 'refund': article title + help category (read-only).

Deterministic only: no LLM calls. Ground truth is hardcoded below and never
appears in tasks.jsonl.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_lib import (  # noqa: E402
    Judge,
    check_read_only,
    check_trajectory_identity,
    check_visited_path,
    contains_all,
    contains_word,
    fail_closed,
    final_answer,
    load_run,
    normalized_url_path,
    parse_args,
    resolve_snapshots,
    site_urls,
)


TASK_ID = "Amtrak--16"
ARTICLE_PATH = "/help/refunds-and-credits"
TITLE = "Refund language used in the mirror"
CATEGORY = "Refunds"


def run_checks(judge: Judge, trajectory: dict, initial_db: str, after_db: str) -> None:
    check_trajectory_identity(judge, trajectory, TASK_ID)
    answer = final_answer(trajectory)
    searched = any(
        normalized_url_path(url) in ("/help", "/search")
        and any("refund" in v.casefold() for v in parse_qs(urlparse(url).query).get("q", []))
        for url in site_urls(trajectory)
    )
    judge.check("performed_refund_search", searched, "required=/help?q=<refund...> or /search?q=<refund...>")
    check_visited_path(judge, trajectory, "visited_refund_article", ARTICLE_PATH)
    judge.check("answer_has_exact_title", contains_all(answer, [TITLE]), f"expected={TITLE!r}, answer={answer!r}")
    judge.check("answer_has_category", contains_word(answer, CATEGORY), f"expected={CATEGORY!r}, answer={answer!r}")
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
