#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--35.

React latest release version and publish date.

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
    j = Judge('GitHub--35', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_react_repo", visited_repo(t, "facebook/react"),
            "opened react (releases page or repo page — both carry the version/date)")
    j.check("answer_version", contains_any(fa, ["18.3.1", "v18.3.1"]), f"final={fa[:160]!r}")
    j.check("answer_date", mentions_date(fa, "2024-04-26"), f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
