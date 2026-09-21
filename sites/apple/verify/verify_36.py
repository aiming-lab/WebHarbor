#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--36.

Task: Browse Apple Music on the entertainment section of the Apple's website, and see which singers' names are included in the pictures on this page.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /music (Entertainment > Apple Music) shows eight featured-artist cards:
    Taylor Swift, Drake, The Weeknd, Billie Eilish, Dua Lipa, Olivia
    Rodrigo, Bad Bunny, Harry Styles.
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
    j = Judge('Apple--36', a.no_llm)
    t, fa = grade_common(j, a)
    nav = navigated_path(t, "/music")
    j.check("nav_apple_music", nav, "expected /music")
    artists = ["taylor swift", "drake", "the weeknd", "billie eilish", "dua lipa",
               "olivia rodrigo", "bad bunny", "harry styles"]
    found = sum(1 for a in artists if contains_any(fa, [a]))
    j.check("answer_six_plus_artists", found >= 6, f"artists matched={found}")
    j.emit()


if __name__ == "__main__":
    main()
