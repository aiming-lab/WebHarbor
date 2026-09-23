#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--10 (read-only).

Browse Adjunct via the Employment Level filter, then narrow to Texas with
the location filter; report how many adjunct jobs in Texas the site lists.
Accepted honest narrowing paths (both real on-site navigation):
  - the location filter field on the adjunct browse page (radialtown=Texas),
  - the chained Texas facet URL (/jobs/adjunct/texas/ or /jobs/texas/adjunct/).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, site_urls, check_trajectory_identity, browse_visited, check_account_section, check_browse, check_career_article,  # noqa: E402
                        check_detail_visited, check_employer_hub, check_location_search, check_only_rows_added,
                        check_only_rows_removed, check_read_only, check_row_edited_only_in, check_search,
                        check_signed_in_as, check_visited_path, contains_all, contains_any, contains_dollar_amount,
                        contains_month_date, contains_number, fail_closed, final_answer, load_run, parse_args,
                        resolve_snapshots, rows_where)

TASK_ID = "Chronicle Jobs--10"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_browse(j, t, "browsed_adjunct", "adjunct")
    urls = site_urls(t)
    ok_tx = (any("radialtown" in u and "texas" in u.lower() for u in urls)
             or any("/jobs/" in u and "adjunct" in u and "texas" in u for u in urls))
    j.check("narrowed_to_texas", ok_tx,
            "required: the adjunct results narrowed to Texas via the location filter field "
            "(radialtown=Texas) or the chained Texas facet URL")
    fa = final_answer(t)
    j.check("answer_has_count", contains_number(fa, 7), f"expected=7 answer={fa[:200]!r}")
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
    except Exception as exc:  # noqa: BLE001 — any verifier error fails closed
        fail_closed(TASK_ID, "verifier_error", f"{type(exc).__name__}: {exc}")
    j.emit()


if __name__ == "__main__":
    main()
