#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--34.

'Protein prediction' project with the highest number of forks.

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
    j = Judge('GitHub--34', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["protein"]) or visited_repo(t, "deepmind/alphafold"))
    j.check("nav_protein_search_or_repo", nav, "protein search or the repo page")
    j.check("answer_names_alphafold", contains_any(fa, ["alphafold"]), f"final={fa[:160]!r}")
    j.check("answer_cits_forks",
            figure_mentioned(fa, "2.2", 2200)
            or contains_any(fa, ["most forked", "highest number of forks", "most-forked"]),
            f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
