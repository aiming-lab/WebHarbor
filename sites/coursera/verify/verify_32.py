#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--32.

Search for 'Data Analysis' courses; apply Beginner Level and 1-3 Months duration filters; determine the total count of matching courses.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): search q=Data Analysis + level=Beginner + duration=1-3_months returns exactly 4 results: Data Analysis and Visualization with Excel and Cognos; Python for Data Science, AI & Development; Python Data Science Fundamentals; Business Process Management.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
filtered search navigation | page shows the four results | answer states 4
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (parse_args, load_task, check_read_only, grade_options,
                        course_option_ok, search_card_ok,
                        navigated_to, navigated_any, navigated_to_course, query_has, page_text_at,
                        contains_all, contains_any, counts, has_number, numbers_in,
                        pct_of, star_level_lowest, re_found, fold, is_mirror_url,
                        states_no_other_courses,
                        step_urls, _url_path)


def main():
    a = parse_args()
    j, t, fa = load_task(a, "Coursera--32")
    j.check("nav_filtered_search",
            navigated_to(t, "/search") and query_has(t, "level=beginner")
            and query_has(t, "duration=1-3_months") and query_has(t, "data analysis"),
            "trajectory must include the Data Analysis search with Beginner and 1-3 Months filters")
    page = page_text_at(t, "/search")
    four = ["Data Analysis and Visualization with Excel and Cognos",
            "Python for Data Science, AI & Development",
            "Python Data Science Fundamentals", "Business Process Management"]
    j.check("page_shows_results", contains_all(page, four),
            "filtered search page must show all four results")
    j.check("answer_count", counts(fa, 4, "course", "courses", "result", "results",
                                   "match", "matches"),
            "answer must state that 4 courses match")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
