#!/usr/bin/env python3
"""Deterministic verifier for Chronicle Jobs--4 (read-only).

Location-only search for Boston (keywords empty); report the total found and
the title of one tenure-track / professor position in the results.
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

TASK_ID = "Chronicle Jobs--4"


def run_checks(j, t, initial_db, after_db):
    check_trajectory_identity(j, t, TASK_ID)
    check_location_search(j, t, "location_searched_boston", ["Boston"])
    fa = final_answer(t)
    j.check("answer_has_total", contains_number(fa, 65), f"expected=65 answer={fa[:200]!r}")
    prof_titles = ['Ashton B. Carter Visiting Professor', 'Assistant Professor (Urban Economics)', 'Assistant Professor of Lighting', 'Assistant Professor or as Associate Professor without Tenure', 'Assistant Professor/Associate Professor/Professor (Open Rank), School of Law - Health Policy and Law', 'Associate Professor of Music; Applied Collaborative Piano', 'Cummings Family Professor of the Practice in Entrepreneurship, Director Derby Entrepreneurship Cntr', 'Cummings Foundation Professor of Global Health Equity', 'Endowed Bartlett Chair Professor/Associate Professor, Free Enterprise', 'Endowed Bartlett Chair Professor/Associate Professor, Free Speech', 'Endowed Nursing Professorship in Health, Well-Being, and Chronic Conditions Innovation', 'Geospatial/ AI Faculty: Assistant Professor', 'Mark and Gail Pyke Professor of Finance Professorship', 'Maureen and Craig Sullivan University Professor', 'Professorship in World Christianity', 'Tenure-Track Professor in Life Science and AI', 'Tenure-Track or Tenured Professor in Ukrainian Studies, Harvard University', 'Tenured Professor in Statistics, Harvard', 'Tenured-Track Professorship in Buddhist Studies']
    
    j.check("answer_names_professor_title", contains_any(fa, prof_titles),
            f"expected one of {len(prof_titles)} professor/tenure-track Boston titles answer={fa[:200]!r}")
    check_read_only(j, initial_db, after_db)


def main():
    from composed_grade import grade
    grade(4)


if __name__ == "__main__":
    main()
