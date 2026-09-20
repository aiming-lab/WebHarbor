#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--4.

Search for the cheapest hotel near Kashi Vishwanath Temple that offers
breakfast, Dec 25-26.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The query "Kashi Vishwanath Temple" resolves to Varanasi; six Varanasi
    properties include breakfast. Cheapest overall: Kashi Vishwanath Guest
    House ($53 list / $37 discounted with 30% off, breakfast included).
    Cheapest property typed "Hotel": Rivatas by Ideal Varanasi ($95,
    breakfast included). Both readings are accepted; any other property is
    more expensive on the mirror.

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

ALLOWED = {
    "Kashi Vishwanath Guest House": ["Kashi Vishwanath Guest House", "Kashi Vishwanath Guesthouse", "kashi vishwanath guest"],
    "Rivatas by Ideal Varanasi": ["Rivatas by Ideal Varanasi", "Rivatas"]
}
PRICES = {
    "Kashi Vishwanath Guest House": [37, 37.1, 53],
    "Rivatas by Ideal Varanasi": [95],
}


def main():
    a = parse_args()
    j = Judge('Booking--4', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_kashi_search_or_prop",
            search_url_with(t, ["kashi"]) or visited_property(t, "kashi-vishwanath-guest-house-varanasi")
            or visited_property(t, "rivatas-by-ideal-varanasi-varanasi"),
            "the Kashi Vishwanath results (breakfast filter) or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_cheapest", bool(named), f"final={fa[:200]!r}")
    if named:
        j.check("answer_price", any(price_in(fa, p) for p in PRICES[named]),
                f"final={fa[:200]!r} accepted={PRICES[named]}")
    else:
        j.check("answer_price", False, "no named property")
    j.check("answer_mentions_breakfast", contains_any(fa, ["breakfast"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
