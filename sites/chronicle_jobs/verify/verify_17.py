#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--17 (stateful (carol shortlist)).

Log in as carol.d@test.com, save 'Dean, College of Business' at Missouri
State University, report the new total saved count. DB: exactly one saved_jobs
row added for carol + that job.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_trajectory_identity, browse_visited, search_visited, detail_visited, check_account_section, check_browse, check_career_article,  # noqa: E402
                        check_detail_visited, check_employer_hub, check_location_search, check_only_rows_added,
                        check_only_rows_removed, check_read_only, check_row_edited_only_in, check_search,
                        check_signed_in_as, check_visited_path, contains_all, contains_any, contains_dollar_amount,
                        contains_month_date, contains_number, fail_closed, final_answer, load_run, parse_args,
                        resolve_snapshots, rows_where)

TASK_ID = "Chronicle Jobs--17"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_signed_in_as(j, t, "carol.d@test.com")
    # The task says "Save the job ... then report the count" — it does not
    # require OPENING the detail page: the site's search cards expose a Save
    # button to signed-in users, so finding the job on-site via search/browse
    # plus the exact saved_jobs delta is the honest completion contract.
    found_job = search_visited(t, all_tokens=["Dean", "College", "Business"]) or detail_visited(t, 38026496, "dean-college-of-business")
    j.check("found_job_on_site", found_job,
            "required: a search/browse surfacing the job or its detail page; "
            f"observed={[u for u in __import__('verify_lib').site_urls(t) if 'Keywords' in u or '/job/' in u][:5]!r}")
    def _is_carol_save(r):
        return (int(r["user_id"]) == 3 and int(r["job_id"]) == 2
                and "Dean, College of Business" in str(rows_where(after_db, "jobs", "id = ?", (int(r["job_id"]),))[0]["title"]))
    check_only_rows_added(j, initial_db, after_db, "saved_jobs", 1, predicate=_is_carol_save, label="shortlist")
    fa = final_answer(t)
    j.check("answer_has_total", contains_number(fa, 6), f"expected=6 answer={fa[:200]!r}")


def main():
    from composed_grade import grade
    grade(17)


if __name__ == "__main__":
    main()
