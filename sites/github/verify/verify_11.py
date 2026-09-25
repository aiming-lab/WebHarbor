#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--11.

Climate-change project initiated January 2023: language and description.

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

# Qualifying set served by /search?q=climate change created:2023-01-01..2023-01-31.
QUALIFIERS = {
    "climate-viz/climate-change-dashboard": ("javascript", ["dashboard", "d3", "visualization", "temperature", "emission"]),
    "eco-2023/climate-tracker": ("python", ["tracker", "emissions", "temperature"]),
    "jan23-climate/global-warming-watch": ("typescript", ["dashboard", "global warming", "watch"]),
    "green-2023/january-climate-viz": ("javascript", ["visualizing", "visualization"]),
    "jan23-co2/co2-emissions-2023": ("python", ["co2", "emissions", "tracker"]),
    "jan23-iot/climate-iot-sensors": ("c++", ["iot", "sensor", "firmware"]),
}

def main():
    a = parse_args()
    j = Judge('GitHub--11', a.no_llm)
    t, fa = grade_common(j, a)

    nav = ((search_url_with(t, ["climate"]) and
            (navigated_to(t, "created:") or search_url_with(t, ["2023-01"])))
           or visited_repo_any(t, list(QUALIFIERS)))
    j.check("nav_created_jan2023_search_or_repo", nav,
            "climate search with a created:2023-01 constraint, or a qualifying repo page")
    named = mentions_any_repo(fa, list(QUALIFIERS))
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")
    if named:
        lang, toks = QUALIFIERS[named]
        j.check("answer_states_language", contains_any(fa, [lang]), f"expected {lang!r}")
        j.check("answer_describes_project", contains_any(fa, toks), f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
