#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--33.

Customer Stories: list the 2 stories on the page.

Ground truth is hardcoded here and nowhere in tasks.jsonl; it was read off the
served pages of the running mirror container (all "last N days" filters anchor
to the site's frozen date 2024-05-15).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_repo,
                        visited_repo_any, search_url_with, step_urls, decoded,
                        contains_all, contains_any, mentions_repo, mentions_any_repo,
                        has_number, counts, figure_mentioned, mentions_date, Judge,
                        parse_args)



def main():
    a = parse_args()
    j = Judge('GitHub--33', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_customer_stories", navigated_to(t, "/customer-stories"),
            "opened the Customer Stories page")
    j.check("answer_lists_both_stories",
            contains_any(fa, ["mercedes-benz", "mercedes benz", "mercedes"])
            and contains_any(fa, ["shopify"]),
            f"final={fa[:200]!r}")

    j.emit()

if __name__ == "__main__":
    main()
