#!/usr/bin/env python3
"""Deterministic verifier for Coursera task Coursera--29.

Browse the Coursera website and find the price for one year of Coursera Plus, the discount, and 3 companies that work with Coursera.

Ground truth (frozen from the audited mirror pages; hard-coded here, never in
tasks.jsonl): Coursera Plus annual subscription: $399/year, 'Save $309/year (43% off vs. monthly)'; partner companies include Google, IBM, Meta, Microsoft, AWS, Salesforce, Atlassian, Canva, PwC, Commonwealth Bank, Macquarie Bank, DeepLearning.AI, EIT Digital.

Checks (deterministic only; --no_llm skips the unused anchored LLM utilities):
coursera-plus page navigation | page shows the pricing | answer states 399 + discount (309 or 43%) + >=3 company names
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
    j, t, fa = load_task(a, "Coursera--29")
    page = page_text_at(t, "/coursera-plus")
    j.check("nav_coursera_plus", navigated_to(t, "/coursera-plus"),
            "trajectory must open the Coursera Plus page")
    j.check("page_shows_pricing", contains_all(page, ["$399", "$309"]),
            "observed DOM must show the annual price and the discount")
    j.check("answer_year_price", contains_all(fa, ["399"]),
            "answer must state the one-year price ($399)")
    j.check("answer_discount", contains_all(fa, ["309"]) or pct_of(fa, 43),
            "answer must state the discount ($309 / 43% off)")
    companies = ["Google", "IBM", "Meta", "Microsoft", "AWS", "Amazon Web Services",
                "Salesforce", "Atlassian", "Canva", "PwC", "Commonwealth Bank",
                "Macquarie Bank", "DeepLearning.AI", "Deeplearning.AI", "EIT Digital",
                "Airbus", "Oréal", "Oreal", "Merck", "Tata", "Danone",
                "Petrobras", "Leidos", "Unilever", "Accenture"]
    found = [c for c in companies if contains_all(fa, [c])]
    j.check("answer_lists_three_companies", len(found) >= 3,
            f"companies found={found}")
    check_read_only(j, a)
    j.emit()


if __name__ == "__main__":
    main()
