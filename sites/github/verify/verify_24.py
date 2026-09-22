#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--24.

angular repo: last three issues closed.

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
    j = Judge('GitHub--24', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_angular_issues_closed",
            navigated_to(t, "/angular/angular/issues") and navigated_to(t, "closed"),
            "opened angular's closed-issues list")
    j.check("answer_lists_last_three_closed",
            contains_any(fa, ["infinite loop"])
            and contains_any(fa, ["dirty"])
            and contains_any(fa, ["template type checker", "type checker"]),
            f"final={fa[:200]!r}")

    j.emit()

if __name__ == "__main__":
    main()
