#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--28.

Find the search settings for Google Map, what options are shown on that page?

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The /settings page ('Search Settings') offers: Distance units (Kilometers
    (km) / Miles (mi)); Language (English, Espanol, Francais, Deutsch, Japanese,
    Chinese, Korean, Portuguese, Italiano, Arabic); Default location (free-text
    home/work address); Map type (Default / Satellite / Terrain); Accessibility
    (Prefer wheelchair-accessible routes); a 'Save settings' button (demo mode).
    Source: /settings.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the /settings page | answer describes at least three of the settings
  option groups | read-only DB
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, navigated_to, navigated_any, navigated_phrase,
                        visited_place, visited_any_place, name_in, count_names,
                        contains_all, contains_any, distance_claim, minutes_claim,
                        number_claim, rating_order_ok, extract_mi_values, numbers_in)

def main():
    a = parse_args()
    j = Judge('Google Map--28', a.no_llm)
    t, fa = grade_common(j, a)
    OPTIONS = ["distance units", "kilometers", "miles", "language", "default location",
               "map type", "satellite", "terrain", "accessibility", "wheelchair"]
    j.check("nav_settings_page", navigated_to(t, "/settings"),
            "the /settings page in the trajectory")
    matched = sum(1 for tok in OPTIONS if contains_any(fa, [tok]))
    j.check("answer_describes_settings_options", matched >= 3,
            f"matched={matched} final={fa[:250]!r}")
    j.emit()

if __name__ == "__main__":
    main()
