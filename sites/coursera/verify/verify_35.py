#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--35.

Find a Coursera course on Sustainable Agriculture practices; detail the course's objectives and the background of the lead instructor.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Sustainable Agricultural Land Management (University of Florida, Ann Wilkie - Professor); Sustainable Agricultural Land Practices for Climate Resilience (CU Boulder, Karen Goff); Sustainable Agricultural Land Management for Smallholder Farms (Australian National University, Mark Howden); Regenerative Agriculture and Soil Health Specialization (CU Boulder, Joel Salatin).

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
course-detail navigation | page shows the course | answer names course + instructor + >=2 objectives + partner
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
    j, t, fa = load_task(a, "Coursera--35")
    ob_ufl = [["sustainable farming practices"], ["soil health"], ["Conserve water"], ["agroforestry"]]
    ob_cu = [["cover crop rotation"], ["soil carbon"], ["resilience"]]
    ob_anu = [["soil amendments"], ["smallholder"]]
    ob_reg = [["regenerative practices"], ["soil organic matter"], ["crop rotation"]]
    def cov(groups):
        return sum(1 for g in groups if any(contains_all(fa, [a]) for a in g))
    n_ufl, n_cu, n_anu, n_reg = cov(ob_ufl), cov(ob_cu), cov(ob_anu), cov(ob_reg)
    opts = [
        {"slug": "sustainable-agricultural-land-management",
        "page_tokens": ['Sustainable Agricultural Land Management'],
        "answer_tokens": ['Sustainable Agricultural Land Management', 'Ann Wilkie', 'Florida'],
        "extra": [("answer_objectives", n_ufl >= 2, f"objectives matched={n_ufl}/4 of {ob_ufl}")]},
        {"slug": "sustainable-agricultural-land-practices-climate-cuboulder",
        "page_tokens": ['Sustainable Agricultural Land Practices for Climate Resilience'],
        "answer_tokens": ['Sustainable Agricultural Land Practices', 'Karen Goff', 'Colorado'],
        "extra": [("answer_objectives", n_cu >= 2, f"objectives matched={n_cu}/3 of {ob_cu}")]},
        {"slug": "sustainable-agricultural-land-smallholder-anu",
        "page_tokens": ['Sustainable Agricultural Land Management for Smallholder Farms'],
        "answer_tokens": ['Smallholder Farms', 'Mark Howden', 'Australian National'],
        "extra": [("answer_objectives", n_anu >= 2, f"objectives matched={n_anu}/2 of {ob_anu}")]},
        {"slug": "regenerative-agriculture-soil-health-specialization",
        "page_tokens": ['Regenerative Agriculture and Soil Health Specialization'],
        "answer_tokens": ['Regenerative Agriculture', 'Joel Salatin', 'Colorado'],
        "extra": [("answer_objectives", n_reg >= 2, f"objectives matched={n_reg}/3 of {ob_reg}")]},
    ]
    grade_options(j, t, fa, opts)
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
