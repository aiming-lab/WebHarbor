#!/usr/bin/env python3
"""Deterministic verifier for GitHub task GitHub--36.

'AI agriculture' project created in 2022: language and description.

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

# Qualifying set: served results of /search?q=ai agriculture
# created:2022-01-01..2022-12-31 whose description affirms AI (the served
# IoT-only / traditional / AI-free distractors are excluded).
QUALIFIERS = {
    "agritech/ai-agriculture-platform": ["precision agriculture", "crop disease",
                                         "yield prediction", "disease detection"],
    "smartfarm/crop-ai-vision": ["computer vision", "pest", "yield", "crop"],
    "crop-2022/crop-monitoring-ai-2022": ["drone", "imagery", "field health", "monitoring"],
    "pest-2022/pest-detection-ai": ["pest", "classifier", "image"],
    "weather-2022/farm-weather-ml": ["weather", "forecast", "micro"],
    "livestock-2022/livestock-ai-tracker": ["livestock", "cattle", "computer vision"],
    "yield-2022/yield-prediction-ml": ["yield prediction", "weather", "soil", "satellite"],
    "soil-2022/soil-analysis-ai": ["soil", "spectroscopy", "nutrient"],
    "irrigation-2022/irrigation-ai-controller": ["irrigation", "sprinkler", "moisture"],
}

def main():
    a = parse_args()
    j = Judge('GitHub--36', a.no_llm)
    t, fa = grade_common(j, a)

    nav = ((search_url_with(t, ["agriculture"]) and
            (navigated_to(t, "created:") or search_url_with(t, ["2022"])))
           or visited_repo_any(t, list(QUALIFIERS)))
    j.check("nav_created_2022_search_or_repo", nav,
            "agriculture search with a created:2022 constraint, or a qualifying repo page")
    named = mentions_any_repo(fa, list(QUALIFIERS))
    j.check("answer_names_qualifying_repo", named is not None, f"final={fa[:160]!r}")
    if named:
        j.check("answer_states_language", contains_any(fa, ["python"]),
                "every qualifying AI-agriculture repo is Python")
        j.check("answer_describes_project", contains_any(fa, QUALIFIERS[named]),
                f"final={fa[:160]!r}")

    j.emit()

if __name__ == "__main__":
    main()
