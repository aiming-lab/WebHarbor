#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--4.

Popular JavaScript repo created in the last 30 days with a README.

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

# Qualifying set served by /search?q=language:javascript created:>2024-04-15
# &has_readme=1&sort=stars — the 'popular' bar is >=1,000 stars (8 members).
QUALIFIERS = [
    "big-js-fresh/turbo-front", "apr24-js/hono-extras-2024", "may24-js/oxlint-js",
    "js-hack/quickstart-js-framework", "webspeed/fastjs", "jsxyz/modern-js-tools",
    "vue-utils/reactive-store", "ext-fresh/browser-tab-saver",
]

def main():
    a = parse_args()
    j = Judge('GitHub--4', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["javascript", "created"])
           or visited_repo_any(t, QUALIFIERS))
    j.check("nav_created_js_search_or_repo", nav,
            "JS search with a created constraint, or a qualifying repo page")
    named = mentions_any_repo(fa, QUALIFIERS)
    j.check("answer_names_popular_qualifying_repo", named is not None, f"final={fa[:160]!r}")
    j.check("answer_notes_readme_or_stars",
            contains_any(fa, ["readme", "read me"]) or
            any(figure_mentioned(fa, k, f) for k, f in
                [("5.4", 5400), ("4.1", 4100), ("3.7", 3700), ("3.5", 3500),
                 ("2.5", 2500), ("1.8", 1800), ("1.5", 1500), ("1.2", 1200)]),
            f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
