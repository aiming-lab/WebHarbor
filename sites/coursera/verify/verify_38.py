#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--38.

Browse Coursera: which universities and companies from Australia are partners of Coursera? List all of them.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): The partners page filtered by country=Australia lists 16 partners: Atlassian, Australian National University, Canva, Commonwealth Bank, Deakin University, Macquarie Bank, Macquarie University, Monash University, PwC, RMIT University, UNSW Sydney, University of Adelaide, University of Melbourne, University of Queensland, University of Sydney, University of Western Australia.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
partners?country=Australia navigation | page shows the heading | answer lists >=14 of the 16 partner names
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
    j, t, fa = load_task(a, "Coursera--38")
    j.check("nav_partners_page", navigated_to(t, "/partners"),
            "trajectory must open the partners page (Australia filter or full list)")
    page = page_text_at(t, "/partners")
    j.check("page_shows_partners",
            contains_all(page, ["Our Partners", "Australian National University"]),
            "observed DOM must show the partners list incl. Australian partners")
    partners = ["Atlassian", "Australian National University", "Canva",
                "Commonwealth Bank", "Deakin University", "Macquarie Bank",
                "Macquarie University", "Monash University", "PwC", "RMIT University",
                "UNSW Sydney", "University of Adelaide", "University of Melbourne",
                "University of Queensland", "University of Sydney",
                "University of Western Australia"]
    found = [p for p in partners if contains_all(fa, [p])]
    missing = [p for p in partners if p not in found]
    j.check("answer_lists_australian_partners", len(found) >= 14,
            f"partners found={len(found)}/16; missing={missing}")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
