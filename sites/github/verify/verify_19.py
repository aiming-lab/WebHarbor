#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--19.

Most recently updated Python repo tagged 'web scraping' with 100+ stars.

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
    j = Judge('GitHub--19', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["scraping"])
           or visited_repo(t, "reddit-scrape/reddit-web-scraper-py"))
    j.check("nav_webscraping_search_or_repo", nav,
            "web-scraping search or the most-recently-updated repo page")
    j.check("answer_names_reddit_scraper",
            mentions_repo(fa, "reddit-scrape/reddit-web-scraper-py"),
            f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
