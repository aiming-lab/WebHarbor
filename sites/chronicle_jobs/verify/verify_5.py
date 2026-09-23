#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--5 (read-only).

Browse the '$200,000 or more' salary band; report how many jobs are in the
band plus two of them with their dollar amounts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, check_trajectory_identity, browse_visited, check_account_section, check_browse, check_career_article,  # noqa: E402
                        check_detail_visited, check_employer_hub, check_location_search, check_only_rows_added,
                        check_only_rows_removed, check_read_only, check_row_edited_only_in, check_search,
                        check_signed_in_as, check_visited_path, contains_all, contains_any, contains_dollar_amount,
                        contains_month_date, contains_number, fail_closed, final_answer, load_run, parse_args,
                        resolve_snapshots, rows_where)

TASK_ID = "Chronicle Jobs--5"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_browse(j, t, "browsed_salary_band", "-200-000-or-more")
    fa = final_answer(t)
    j.check("answer_has_band_total", contains_number(fa, 19), f"expected=19 answer={fa[:200]!r}")
    band = [('Provost', '$385,000 to $425,000'), ('Provost', '$400,000'), ('Vice President for Member Engagement', '$200,000 and $240,000'), ('President', '$235,000.00 - $290,000.00'), ('Assistant Vice President & Chief Budget Officer', '$200,000 - $230,000'), ('Provost & Chief Academic Officer', '$300,000'), ('Director, School of Education', '$215,000-$225,000'), ('Internal Medicine Staff Physician', '$203,320.00 - $305,032.00'), ('President', '$450,000 to $700,000'), ('Dean, College of Osteopathic Medicine', '$350,000 – $430,000'), ('Cummings Foundation Professor of Global Health Equity', 'Minimum of $230,000; actual depends on evaluation of experience and qualifications.'), ('President', '$310,000 - $350,000'), ('Pediatric Neurosurgeon --Assistant or Associate Professor, WOT', '$575,000-$849,948/year'), ('Spine Neurosurgeon-- Assistant or Associate Professor, WOT', '$360,000-$849,948/year'), ('Vice Chancellor, Human Resources and Employee Relations', '$212,312.00 - $268,928.00 Annually'), ('Academic Acute Pain Anesthesiologist', 'The salary range for this position is $450,000-$600,000. This position includes membership in the H'), ('Vice President for University Marketing and Communication', '$250,000 - $300,000'), ('Maureen and Craig Sullivan University Professor', '$200,000-$250,000'), ('Chief Academic Officer/Provost', '$200,000–$240,000')]
    
    ok_pairs = 0
    import re as _re
    for title, salary in band:
        m = _re.search(r"\$[\d][\d,]*(?:\.\d\d)?", salary)
        if not m:
            continue
        first_amount = m.group(0)
        if contains_all(fa, [title[:48]]) and contains_dollar_amount(fa, first_amount):
            ok_pairs += 1
    j.check("answer_names_two_band_jobs_with_amounts", ok_pairs >= 2,
            f"pairs_matched={ok_pairs} answer={fa[:300]!r}")
    check_read_only(j, initial_db, after_db)


def main():
    from composed_grade import grade
    grade(5)


if __name__ == "__main__":
    main()
