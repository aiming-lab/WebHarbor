#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--42.

Search for a Hokkaido hotel March 1-7 2024 with rating 9+; check its user
reviews: which categories are greater than 9 and which are less than 9?

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The query "Hokkaido" resolves to Sapporo. Sapporo 9+ properties (5) each
    carry a Categories block on their page splitting their review sub-scores
    into 'Categories above 9.0' and 'Categories below 9.0'. The verifier
    grades the category split of the hotel the run opened and named.

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
    "JR Tower Hotel Nikko Sapporo": [
        "JR Tower Hotel Nikko Sapporo"
    ],
    "Cross Hotel Sapporo": [
        "Cross Hotel Sapporo"
    ],
    "Keio Plaza Hotel Sapporo": [
        "Keio Plaza Hotel Sapporo"
    ],
    "Dormy Inn Premium Sapporo": [
        "Dormy Inn Premium Sapporo"
    ],
    "Hotel Okura Sapporo": [
        "Hotel Okura Sapporo"
    ]
}
SLUGS = ["jr-tower-hotel-nikko-sapporo-sapporo", "cross-hotel-sapporo-sapporo", "keio-plaza-hotel-sapporo-sapporo", "dormy-inn-premium-sapporo-sapporo", "hotel-okura-sapporo-sapporo"]
REVIEW_SCORES = {
    "JR Tower Hotel Nikko Sapporo": {
        "Cleanliness": 9.3,
        "Comfort": 9.0,
        "Staff": 9.4,
        "Facilities": 8.7,
        "Location": 9.2,
        "Value for money": 8.6,
        "Free WiFi": 9.0
    },
    "Cross Hotel Sapporo": {
        "Cleanliness": 9.6,
        "Comfort": 9.3,
        "Staff": 9.7,
        "Facilities": 9.0,
        "Location": 9.5,
        "Value for money": 8.9,
        "Free WiFi": 9.3
    },
    "Keio Plaza Hotel Sapporo": {
        "Cleanliness": 9.3,
        "Comfort": 9.7,
        "Staff": 9.4,
        "Facilities": 9.4,
        "Location": 9.9,
        "Value for money": 9.3,
        "Free WiFi": 9.7
    },
    "Dormy Inn Premium Sapporo": {
        "Cleanliness": 9.9,
        "Comfort": 9.6,
        "Staff": 10.0,
        "Facilities": 9.3,
        "Location": 9.7,
        "Value for money": 9.2,
        "Free WiFi": 9.6
    },
    "Hotel Okura Sapporo": {
        "Cleanliness": 9.7,
        "Comfort": 9.5,
        "Staff": 9.8,
        "Facilities": 9.1,
        "Location": 9.6,
        "Value for money": 9.0,
        "Free WiFi": 9.5
    }
}


CATEGORY_TOKENS = {
    "Cleanliness": ["cleanliness"],
    "Comfort": ["comfort"],
    "Staff": ["staff"],
    "Facilities": ["facilities"],
    "Location": ["location"],
    "Value for money": ["value for money", "value"],
    "Free WiFi": ["free wifi", "wifi"],
}
ABOVE_RX = r"(?:above|greater than|higher than|over)\s*(?:9(?:\.0)?)?\s*(?:points?)?\s*[:\-\u2013]?"
BELOW_RX = r"(?:below|less than|lower than|under)\s*(?:9(?:\.0)?)?\s*(?:points?)?\s*[:\-\u2013]?"


def _classify(f):
    import re as _re
    above_m = list(_re.finditer(ABOVE_RX, f))
    below_m = list(_re.finditer(BELOW_RX, f))
    spans = [(m.start(), m.end(), "above") for m in above_m] + [(m.start(), m.end(), "below") for m in below_m]
    spans.sort()
    segs = []
    for i, (s, e, kind) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else len(f)
        segs.append((kind, f[e:end]))
    return segs


def main():
    a = parse_args()
    j = Judge('Booking--42', a.no_llm)
    t, fa = grade_common(j, a)
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {len(ALLOWED)} Sapporo 9+ hotels")
    if not named:
        j.emit()
    j.check("nav_hotel_review_page", visited_property(t, dict(zip(ALLOWED, SLUGS))[named]),
            "the named hotel's page (the Categories block renders only there)")
    f = norm(fa)
    hi = {k for k, v in REVIEW_SCORES[named].items() if v >= 9.0}
    lo = {k for k, v in REVIEW_SCORES[named].items() if v < 9.0}
    segs = _classify(f)
    correct, wrong = 0, []
    for kind, seg in segs:
        for cat, tokens in CATEGORY_TOKENS.items():
            if any(tok in seg for tok in tokens):
                if kind == "above" and cat in hi:
                    correct += 1
                elif kind == "below" and cat in lo:
                    correct += 1
                else:
                    wrong.append((kind, cat))
    j.check("answer_category_split", correct >= 2 and not wrong,
            f"final={fa[:400]!r} correctly_classified={correct} misclassified={wrong} "
            f"page_hi={sorted(hi)} page_lo={sorted(lo)}")
    j.emit()


if __name__ == "__main__":
    main()
