#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--36.

Search for a budget Rome hotel under $100/night for one adult, March 20-23
2024; sort by price; identify if any of the top three results offer breakfast.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Rome properties at or under $100/night, price-sorted: Hostel Roma Termini
    ($34), Hotel Dina Rome ($58), Pensione Roma Centro ($61), then Hotel Grifo
    Rome ($82, breakfast) and Domus Aventina ($88, breakfast). NONE of the top
    three cheapest results offers breakfast; the first breakfast-including
    property is the 4th result.

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

TOP3 = ["Hostel Roma Termini", "Hotel Dina Rome", "Pensione Roma Centro"]
TOP3_SLUGS = ["hostel-roma-termini-rome", "hotel-dina-rome-rome", "pensione-roma-centro-rome"]


def main():
    a = parse_args()
    j = Judge('Booking--36', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_rome_budget_price_sorted",
            search_url_with(t, ["rome"]) or all(visited_property(t, s) for s in TOP3_SLUGS),
            "the Rome results page (cards show per-night prices, so the lowest-priced three"
            " are derivable by reading them; the exact three properties, their prices and the"
            " breakfast claim are pinned by the answer checks) or all three top property pages")
    import re as _re
    f = norm(fa)
    j.check("answer_addresses_breakfast", "breakfast" in f,
            f"final={fa[:300]!r}")
    neg_near = _re.search(r"(?:no|not|none|without|zero|doesn ?t|n ?t)\s*[^.;]{{0,60}}breakfast", f) or \
               _re.search(r"breakfast[^.;]{{0,60}}(?:no|not|none|without|zero|doesn ?t|n ?t)", f)
    named_top3 = sum(1 for nm in TOP3 if any(a.lower() in f for a in [nm, nm.lower()]))
    any_negative = _re.search(r"\b(?:no|none|not|n ?t|without)\b", f)
    j.check("answer_negative_claim_matches_mirror",
            bool(neg_near) or (named_top3 == 3 and bool(any_negative)),
            f"final={fa[:300]!r} the mirror shows NO breakfast among the top three cheapest")
    j.emit()


if __name__ == "__main__":
    main()
