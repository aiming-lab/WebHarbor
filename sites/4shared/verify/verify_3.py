#!/usr/bin/env python3
"""Deterministic verifier for 4shared--3 (read-only).

Broad search for garden planning resources; the PDF with three planting zones and a
maintenance calendar on page 49; report filename, page count and uploader.

Checks: identity | searched (garden/planning) | opened the target detail page |
answer has exact filename + 58 pages + uploader | every table unchanged.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_detail_visited, check_read_only, check_search_or_category,  # noqa: E402
                        check_trajectory_identity, contains_all, contains_filename, contains_number,
                        fail_closed, final_answer, load_run, parse_args, resolve_snapshots)

TASK_ID = "4shared--3"
SLUG = "rain-garden-planting-guide-pdf-97"
FILENAME = "Rain Garden Planting Guide.pdf"
PAGES = 58
UPLOADER = "Community Library"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_search_or_category(j, t, "searched_garden_planning", any_tokens=["garden", "planting", "planning"], categories=["documents"])
    check_detail_visited(j, t, SLUG)
    fa = final_answer(t)
    j.check("answer_has_exact_filename", contains_filename(fa, FILENAME), f"expected={FILENAME!r} answer={fa[:200]!r}")
    j.check("answer_has_page_count", contains_number(fa, PAGES), f"expected={PAGES} answer={fa[:200]!r}")
    j.check("answer_has_uploader", contains_all(fa, [UPLOADER]), f"expected={UPLOADER!r} answer={fa[:200]!r}")
    check_read_only(j, initial_db, after_db)


def main():
    a = parse_args()
    try:
        t = load_run(a.run_dir)
    except (OSError, ValueError) as exc:
        fail_closed(TASK_ID, "trajectory_unavailable", str(exc))
    initial_db, after_db = resolve_snapshots(a, TASK_ID)
    j = Judge(TASK_ID, a.no_llm)
    try:
        run_checks(j, t, initial_db, after_db)
    except Exception as exc:  # noqa: BLE001
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    j.emit()


if __name__ == "__main__":
    main()
