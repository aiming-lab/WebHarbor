#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--23.

ohmyzsh wiki: how to change the zsh theme to agnoster.

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
    j = Judge('GitHub--23', a.no_llm)
    t, fa = grade_common(j, a)

    j.check("nav_ohmyzsh_wiki", navigated_to(t, "/ohmyzsh/ohmyzsh/wiki"),
            "opened the ohmyzsh wiki")
    j.check("answer_theme_instructions",
            contains_any(fa, ["agnoster"])
            and (contains_any(fa, ["zsh_theme", "zsh theme"])
                 or contains_any(fa, [".zshrc", "zshrc"]))
            and contains_any(fa, ["source", "reload", "new terminal", "restart"]),
            f"final={fa[:200]!r}")

    j.emit()

if __name__ == "__main__":
    main()
