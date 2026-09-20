#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--31.

Search Rio de Janeiro hotels March 1-7 2024; check the Brands filter: which
brand has the most hotels and which the fewest?

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Rio de Janeiro brand counts as shown in the results sidebar:
    Hilton 4, Marriott 3, Accor 2 — Hilton has the most, Accor the fewest.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (the task is read-only on the mirror).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, grade_booking, navigated_to, navigated_any,
                        visited_property, visited_root, search_url_with,
                        contains_all, contains_any, mentions_one_of, price_in,
                        count_claim, first_mention, norm, step_urls, Judge,
                        parse_args)

MOST_BRAND = "Hilton"
FEWEST_BRAND = "Accor"
MOST_N, FEWEST_N = 4, 2


def main():
    a = parse_args()
    j = Judge('Booking--31', a.no_llm)
    t, fa = grade_common(j, a)
    import re as _re
    j.check("nav_rio_search", search_url_with(t, ["rio"]),
            "the Rio de Janeiro results page (the Brand filter shows per-brand counts)")
    f = norm(fa)
    j.check("answer_names_both_brands",
            MOST_BRAND.lower() in f and FEWEST_BRAND.lower() in f,
            f"final={fa[:300]!r} expected {MOST_BRAND} (most) and {FEWEST_BRAND} (fewest)")

    def _closest_brand_to(word_rx):
        best, bestd = None, 10 ** 9
        for m in _re.finditer(word_rx, f):
            for b in (MOST_BRAND.lower(), FEWEST_BRAND.lower()):
                for bm in _re.finditer(b, f):
                    d = abs(bm.start() - m.start())
                    if d < bestd:
                        best, bestd = b, d
        return best

    def _count_near(brand, n, other):
        for m in _re.finditer(r"(?<![\d.])" + str(n) + r"(?![\d.])", f):
            w = f[max(0, m.start() - 30):m.end() + 30]
            if brand in w and other not in w:
                return True
        return False

    words_ok = (_closest_brand_to(r"most|largest|highest") == MOST_BRAND.lower()
                and _closest_brand_to(r"fewest|smallest|least|lowest") == FEWEST_BRAND.lower())
    counts_ok = (_count_near(MOST_BRAND.lower(), MOST_N, FEWEST_BRAND.lower())
                 and _count_near(FEWEST_BRAND.lower(), FEWEST_N, MOST_BRAND.lower()))
    j.check("answer_most_fewest_direction", words_ok or counts_ok,
            f"final={fa[:300]!r} closest-to-most={_closest_brand_to(r'most|largest|highest')} "
            f"closest-to-fewest={_closest_brand_to(r'fewest|smallest|least|lowest')}")
    j.emit()


if __name__ == "__main__":
    main()
