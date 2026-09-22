#!/usr/bin/env python3
"""Deterministic verifier for 4shared--2 (read-only; task re-anchored by the reviewer).

Search Books for classic fiction; which exact filename has 12 chapters and editorial
notes beginning after page 116? Report its displayed file size.

Checks: identity | searched Books / classic fiction | opened the target detail page
| answer has exact filename + displayed size | every table unchanged.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_detail_visited, check_read_only, check_search_or_category,  # noqa: E402
                        check_trajectory_identity, contains_filename, contains_size, fail_closed,
                        final_answer, load_run, parse_args, resolve_snapshots)

TASK_ID = "4shared--2"
SLUG = "the-time-machine-epub-72"
FILENAME = "The Time Machine.epub"
SIZE = "2.1 MB"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_search_or_category(j, t, "searched_books_classic_fiction", any_tokens=["classic", "fiction", "novel"], categories=["books"])
    check_detail_visited(j, t, SLUG)
    fa = final_answer(t)
    j.check("answer_has_exact_filename", contains_filename(fa, FILENAME), f"expected={FILENAME!r} answer={fa[:200]!r}")
    j.check("answer_has_displayed_size", contains_size(fa, SIZE), f"expected={SIZE!r} answer={fa[:200]!r}")
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
