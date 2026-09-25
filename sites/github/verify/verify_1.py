#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--1.

ML-in-Python decision-trees repo updated within the last 2 days.

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
    j = Judge('GitHub--1', a.no_llm)
    t, fa = grade_common(j, a)

    nav = ((search_url_with(t, ["decision", "updated"]) or search_url_with(t, ["decision", "pushed"]))
           or visited_repo(t, "forest-ai/xgboost-trees"))
    j.check("nav_decision_trees_search_or_repo", nav,
            "decision-trees search with an updated/pushed constraint, or the repo page")
    j.check("answer_names_xgboost_trees",
            mentions_repo(fa, "forest-ai/xgboost-trees"),
            f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
