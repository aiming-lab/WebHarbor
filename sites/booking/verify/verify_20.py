#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--20.

Find a Rome hotel with rating 7+, free cancellation and breakfast included,
for a three-night stay Feb 28 - Mar 2 2024.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
Rome properties with rating >= 7.0, free cancellation and breakfast
    included (3): Hotel de Russie, Domus Aventina, Hotel Grifo Rome.

Checks: run-package gate + non-empty answer + navigation (anti-shortcut) +
answer facts + read-only DB (the task is read-only on the mirror).
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, grade_booking, navigated_to, navigated_any,
                        visited_property, visited_root, search_url_with,
                        contains_all, contains_any, contains_affirmative,
                        mentions_one_of, price_in,
                        count_claim, first_mention, norm, step_urls, Judge,
                        parse_args)

ALLOWED = {
    "Hotel de Russie": [
        "Hotel de Russie"
    ],
    "Domus Aventina": [
        "Domus Aventina"
    ],
    "Hotel Grifo Rome": [
        "Hotel Grifo Rome"
    ]
}
SLUGS = ["hotel-de-russie-rome", "domus-aventina-rome", "hotel-grifo-rome-rome"]


def main():
    a = parse_args()
    j = Judge('Booking--20', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_rome_7_fc_bkf",
            search_url_with(t, ["rome"])
            or any(visited_property(t, s) for s in SLUGS),
            "the Rome results page (cards show ratings and the free-cancellation/breakfast flags) or a qualifying property page; the 7+/fc/breakfast set is enforced by the answer check")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_qualifying_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} qualifying properties")

    j.emit()


if __name__ == "__main__":
    main()
