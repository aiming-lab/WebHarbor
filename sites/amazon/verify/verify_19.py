#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--19.

Look for an English language book on roman empire history in the Amazon Kindle store. Sort by newests arrivals and look for a title that will be released within a month.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The Kindle Store subcategory holds seven roman-empire histories, all
    'Pre-order' with release dates around the catalog snapshot (2026-04-11).
    Released within one month of the snapshot (through 2026-05-11): The Rise of
    Rome (2026-04-23), Caesar's Legacy (2026-04-16), The Twelve Caesars
    (2026-05-09), Pax Romana (2026-04-14), Rome: A History in Seven Sackings
    (2026-05-01), The Complete Roman Empire (2026-04-29). The Fall of Rome
    (2026-05-26) is outside the window. NOTE (quality audit): 'within a month'
    is anchored to the mirror's own catalog timeline, not the wall clock.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (anonymous carts are cookie-backed, so an honest
run leaves the instance DB identical to its seed).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, navigated_to, navigated_any, visited_product,
                        visited_root, search_url_with, contains_all, contains_any,
                        price_in, first_mention, mentions_percent_for, count_claim,
                        extract_color_count_claim, Judge, parse_args)


def main():
    a = parse_args()
    j = Judge('Amazon--19', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    BOOKS = [
        (["rise of rome"], ["april 23", "2026-04-23", "04/23", "4/23"]),
        (["caesar's legacy", "caesar’s legacy"], ["april 16", "2026-04-16", "04/16", "4/16"]),
        (["twelve caesars"], ["may 9", "2026-05-09", "05/09", "5/9"]),
        (["pax romana"], ["april 14", "2026-04-14", "04/14", "4/14"]),
        (["seven sackings"], ["may 1,", "may 1 ", "2026-05-01", "05/01", "5/1"]),
        (["complete roman empire"], ["april 29", "2026-04-29", "04/29", "4/29"]),
    ]
    j.check("nav_roman_kindle_search",
            navigated_to(t, "roman") or visited_product(t, "the-rise-of-rome-a-new-history-of-the-roman-empire"),
            f"urls={[u for u in urls if 'roman' in u.lower()][:4]}")
    matched = [(n, d) for n, d in BOOKS if contains_any(fa, n)]
    j.check("answer_title_within_a_month", bool(matched), f"titles={matched}")
    j.check("answer_release_date_stated",
            any(contains_any(fa, d) for n, d in BOOKS if contains_any(fa, n)),
            "the pre-order release date of the named title")
    j.check("answer_preorder_evidence",
            contains_any(fa, ["pre-order", "preorder", "pre order", "will be released", "released within",
                               "scheduled for release", "release on", "releases on", "released on"]),
            f"final={fa[:260]!r}")
    j.emit()


if __name__ == "__main__":
    main()
