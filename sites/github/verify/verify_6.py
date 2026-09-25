#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--6.

'cryptocurrency wallet' project updated in the past 30 days; top three contributors.

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
    j = Judge('GitHub--6', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_wallet_search", search_url_with(t, ["wallet"]) or search_url_with(t, ["cryptocurrency"]),
            "searched cryptocurrency wallet")
    j.check("nav_contributors_or_repo",
            navigated_to(t, "/cryptolab/crypto-wallet/contributors")
            or visited_repo(t, "cryptolab/crypto-wallet"),
            "opened the most-starred wallet project's contributors page or repo page (sidebar lists the same identities)")
    j.check("answer_top3_contributors",
            contains_any(fa, ["satoshi-fan", "satoshi fan"])
            and contains_any(fa, ["blockchain-dev", "blockchain dev"])
            and contains_any(fa, ["wallet-maintainer", "wallet maintainer"]),
            f"final={fa[:200]!r}")

    j.emit()

if __name__ == "__main__":
    main()
