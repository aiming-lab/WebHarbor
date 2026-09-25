#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--30.

'blockchain technology' project updated in the past 15 days; top five contributors.

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
    j = Judge('GitHub--30', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_blockchain_search", search_url_with(t, ["blockchain"]),
            "searched blockchain technology")
    j.check("nav_contributors_or_repo",
            navigated_to(t, "/blockchain-lab/blockchain-technology/contributors")
            or visited_repo(t, "blockchain-lab/blockchain-technology"),
            "opened the most-starred blockchain project's contributors page or repo page (sidebar lists the same identities)")
    j.check("answer_top5_contributors",
            all(contains_any(fa, [f"chain-dev-{i}", f"chain dev {i}"]) for i in range(1, 6)),
            f"final={fa[:200]!r}")

    j.emit()

if __name__ == "__main__":
    main()
