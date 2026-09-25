#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--32.

Latest C# 'game development' repo with 150+ stars; main features.

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

# 'Latest' pins, both served sorts of
# /search?q=game development language:c# stars:>=150:
#   sort=created -> godot-cs/godot-csharp-starter (most recently created)
#   sort=updated -> unity-multi/unity-mirror-multi (most recently updated)
PINS = {
    "godot-cs/godot-csharp-starter": ["scene management", "player controller",
                                      "networked multiplayer", "godot"],
    "unity-multi/unity-mirror-multi": ["multiplayer", "mirror networking", "mirror",
                                       "unity", "kit"],
}

def main():
    a = parse_args()
    j = Judge('GitHub--32', a.no_llm)
    t, fa = grade_common(j, a)

    nav = (search_url_with(t, ["game"]) or visited_repo_any(t, list(PINS)))
    j.check("nav_gamedev_search_or_repo", nav, "game-development search or a pin repo page")
    named = mentions_any_repo(fa, list(PINS))
    j.check("answer_names_latest_repo", named is not None, f"final={fa[:160]!r}")
    if named:
        j.check("answer_describes_features", contains_any(fa, PINS[named]),
                f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
