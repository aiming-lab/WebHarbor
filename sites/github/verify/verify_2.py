#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--2.

Trending Python repositories, most stars.

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
    j = Judge('GitHub--2', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (navigated_to(t, "/trending") and navigated_to(t, "python")) \
        or visited_repo(t, "tensorflow/tensorflow")
    j.check("nav_trending_python", nav, "trending filtered to Python, or the repo page")
    j.check("answer_names_tensorflow", contains_any(fa, ["tensorflow"]), f"final={fa[:160]!r}")
    j.check("answer_cits_stars", figure_mentioned(fa, "185", 185000), f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
