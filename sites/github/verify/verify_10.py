#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--10.

Copilot Individual: cost per year and features.

Ground truth is hardcoded here and nowhere in tasks.jsonl; it was read off the
served pages of the running mirror container (all "last N days" filters anchor
to the site's frozen date 2024-05-15).
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_repo,
                        visited_repo_any, search_url_with, step_urls, decoded,
                        contains_all, contains_any, mentions_repo, mentions_any_repo,
                        has_number, counts, figure_mentioned, mentions_date, Judge,
                        parse_args)



def main():
    a = parse_args()
    j = Judge('GitHub--10', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_copilot", navigated_to(t, "/features/copilot"), "opened the Copilot page")
    j.check("answer_yearly_cost",
            bool(re.search(r"\$100", fa)) or counts(fa, 100, "usd")
            or counts(fa, 100, "year") or counts(fa, 100, "annually"),
            f"final={fa[:200]!r}")
    j.check("answer_lists_features",
            sum(contains_any(fa, [tok]) for tok in
                ["code completion", "chat", "pull request", "gpt-4o", "claude",
                 "mobile", "third-party", "third party", "code review"]) >= 2,
            f"final={fa[:200]!r}")

    j.emit()

if __name__ == "__main__":
    main()
