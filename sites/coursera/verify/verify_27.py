#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--27.

Search for a Specialization about 'Data Visualization' that includes a project; provide the name, the institution, and the skills developed.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Data Visualization with Tableau Specialization (UC Davis; includes 'Data Visualization with Tableau Project'; skills: Tableau, Dashboard Design, Visual Analytics, Storytelling with Data) or Data Analysis and Visualization with Excel and Cognos (IBM; includes 'Data Visualization Capstone Project'; skills: Excel, IBM Cognos, Dashboard Design, Data Analysis).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
specialization-detail navigation | page shows the project course | answer names specialization + institution + >=2 skills
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
    j, t, fa = load_task(a, "Coursera--27")
    sk_tab = ["Tableau", "Dashboard Design", "Visual Analytics", "Storytelling"]
    sk_exc = ["Excel", "Cognos", "Dashboard Design", "Data Analysis"]
    n_tab = sum(1 for s in sk_tab if contains_all(fa, [s]))
    n_exc = sum(1 for s in sk_exc if contains_all(fa, [s]))
    opts = [
        {"slug": "data-visualization-tableau-specialization",
        "page_tokens": ['Data Visualization with Tableau Specialization', 'Data Visualization with Tableau Project'],
        "answer_tokens": ['Data Visualization with Tableau', 'California, Davis'],
        "card_tokens": ['Data Visualization with Tableau Specialization', 'University of California, Davis'],
        "extra": [("answer_skills", n_tab >= 2, f"skills matched={n_tab}/4 of {sk_tab}")]},
        {"slug": "data-visualization-excel-cognos-specialization",
        "page_tokens": ['Data Analysis and Visualization with Excel and Cognos', 'Data Visualization Capstone Project'],
        "answer_tokens": ['Data Analysis and Visualization with Excel and Cognos', 'IBM'],
        "card_tokens": ['Data Analysis and Visualization with Excel and Cognos', 'IBM'],
        "extra": [("answer_skills", n_exc >= 2, f"skills matched={n_exc}/4 of {sk_exc}")]},
    ]
    via_detail = any(course_option_ok(t, fa, o) for o in opts)
    via_card = search_card_ok(t, fa, opts)
    if via_detail or via_card:
        j.evidence.append('[PASS] evidence_on_mirror: ' +
                          ('course detail page' if via_detail else 'search results card'))
    else:
        grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
