#!/usr/bin/env python3
"""Deterministic verifier for 4shared--1 (read-only).

Browse Images; find the city skyline photo whose detail page lists ISO 200 and
exposure 1/80 s; report exact filename, uploader and resolution.

Checks: identity | browsed Images (or searched skyline) | opened the target detail
page | answer has exact filename + uploader + 3840 x 2160 | every table unchanged.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_detail_visited, check_read_only, check_search_or_category,  # noqa: E402
                        check_trajectory_identity, contains_all, contains_filename, contains_resolution,
                        fail_closed, final_answer, load_run, parse_args, resolve_snapshots)

TASK_ID = "4shared--1"
SLUG = "new-york-skyline-at-sunset-jpg-55"
FILENAME = "New York Skyline at Sunset.jpg"
UPLOADER = "Open Culture Shelf"
WIDTH, HEIGHT = 3840, 2160


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_search_or_category(j, t, "browsed_images", any_tokens=["skyline", "city", "new york", "iso"], categories=["images"])
    check_detail_visited(j, t, SLUG)
    fa = final_answer(t)
    j.check("answer_has_exact_filename", contains_filename(fa, FILENAME), f"expected={FILENAME!r} answer={fa[:200]!r}")
    j.check("answer_has_uploader", contains_all(fa, [UPLOADER]), f"expected={UPLOADER!r} answer={fa[:200]!r}")
    j.check("answer_has_resolution", contains_resolution(fa, WIDTH, HEIGHT), f"expected={WIDTH}x{HEIGHT} answer={fa[:200]!r}")
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
