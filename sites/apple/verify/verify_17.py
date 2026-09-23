#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--17.

Task: Search Apple for the accessory Smart Folio for iPad and check the closest pickup availability next to zip code 90038.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    The Smart Folio pages link to /store/pickup?product=smart-folio-…&zip=…;
    for zip 90038 the stores are Apple The Grove (0.8 miles), Apple Beverly
    Center (1.5 miles), Apple Century City (3.2 miles) — closest is Apple
    The Grove, "Available for pickup" with "Pickup Today: <Smart Folio>".
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, step_urls, url_query, navigated_to,
                        navigated_any, navigated_path, navigated_paths_all,
                        visited_url_with, contains_all, contains_any,
                        contains_word, contains_words_any, price_in,
                        count_named, number_claim, is_jan10_2024, Judge,
                        parse_args)


def main():
    a = parse_args()
    j = Judge('Apple--17', a.no_llm)
    t, fa = grade_common(j, a)
    nav_zip = visited_url_with(t, "/store/pickup", params_sub=[("zip", "90038")])
    j.check("nav_pickup_zip_90038", nav_zip, "expected /store/pickup with zip=90038")
    nav_folio = visited_url_with(t, "/store/pickup", params_sub=[("product", "smart-folio")])
    j.check("nav_pickup_smart_folio", nav_folio,
            "pickup URL must carry a smart-folio product param")
    j.check("answer_closest_store_grove",
            contains_any(fa, ["the grove"]), f"final={fa[:200]!r}")
    j.check("answer_closest_distance",
            contains_any(fa, ["0.8", "closest", "nearest"]), f"final={fa[:200]!r}")
    j.check("answer_available_for_pickup",
            contains_any(fa, ["available", "in stock", "pickup"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
