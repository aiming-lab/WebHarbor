#!/usr/bin/env python3
"""Deterministic verifier for 4shared--4 (read-only).

Broad search for accessibility and design resources; the app package whose detail
page mentions a WCAG contrast preview; report exact filename, version and license.

Checks: identity | searched (accessibility/design) | opened the target detail page |
answer has exact filename + version 5.0.0 + a license shown on the page (the page
shows both the catalog license "Open-source package" and "GPL-3.0" in the notes;
either is accepted) | every table unchanged.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_detail_visited, check_read_only, check_search_or_category,  # noqa: E402
                        check_trajectory_identity, contains_any, contains_filename, fail_closed,
                        final_answer, load_run, normalize_text, parse_args, resolve_snapshots)

TASK_ID = "4shared--4"
SLUG = "colorscope-palette-assistant-zip-44"
FILENAME = "ColorScope Palette Assistant.zip"
VERSION = "5.0.0"
LICENSES = ["GPL-3.0", "GPL 3.0", "GPLv3", "Open-source package"]


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_search_or_category(j, t, "searched_accessibility_design",
                             any_tokens=["accessib", "design", "wcag", "contrast", "palette", "color"], categories=["apps"])
    check_detail_visited(j, t, SLUG)
    fa = final_answer(t)
    j.check("answer_has_exact_filename", contains_filename(fa, FILENAME), f"expected={FILENAME!r} answer={fa[:200]!r}")
    j.check("answer_has_version", VERSION in normalize_text(fa) and "5.0.0" in normalize_text(fa), f"expected={VERSION!r} answer={fa[:200]!r}")
    j.check("answer_has_license", contains_any(fa, LICENSES), f"expected_any={LICENSES!r} answer={fa[:200]!r}")
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
