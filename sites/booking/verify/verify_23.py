#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--23.

Search for a Tokyo hotel with a spa and wellness center rated 9+, five nights
from February 20, 2024; check if free cancellation is offered.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Tokyo 9+/spa properties (4) and their mirror free-cancellation status:
    lyf Shibuya Tokyo (no free cancellation), Mercure Tokyo Haneda Airport
    (free cancellation), TOKYO EAST SIDE HOTEL KAIE (free cancellation),
    Park Hyatt Tokyo (no free cancellation).

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
    "lyf Shibuya Tokyo": [
        "lyf Shibuya Tokyo"
    ],
    "Mercure Tokyo Haneda Airport": [
        "Mercure Tokyo Haneda Airport"
    ],
    "TOKYO EAST SIDE HOTEL KAIE": [
        "TOKYO EAST SIDE HOTEL KAIE"
    ],
    "Park Hyatt Tokyo": [
        "Park Hyatt Tokyo"
    ]
}
SLUGS = ["lyf-shibuya-tokyo-tokyo", "mercure-tokyo-haneda-airport-tokyo", "tokyo-east-side-hotel-kaie-tokyo", "park-hyatt-tokyo-tokyo"]
FC = {
    "lyf Shibuya Tokyo": 0,
    "Mercure Tokyo Haneda Airport": 1,
    "TOKYO EAST SIDE HOTEL KAIE": 1,
    "Park Hyatt Tokyo": 0
}


def main():
    a = parse_args()
    j = Judge('Booking--23', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_tokyo_9_spa",
            (search_url_with(t, ["tokyo", "min_rating=9"]) and search_url_with(t, ["spa=1"]))
            or any(visited_property(t, s) for s in SLUGS),
            "Tokyo results with the 9+/spa filters, or a qualifying property page")
    named = mentions_one_of(fa, list(ALLOWED), ALLOWED)
    j.check("answer_names_hotel", bool(named),
            f"final={fa[:200]!r} expected one of {list(ALLOWED)}")
    if not named:
        j.check("answer_fc_status", False, "no named property")
        j.emit()
    import re as _re
    f = norm(fa)
    windows = []
    for m in _re.finditer(r"free cancellation|cancellation", f):
        windows.append(f[max(0, m.start() - 60):m.end() + 60])
    neg = _re.compile(r"\b(no|not|none|without|doesn ?t|does not|isn ?t|is not|unavailable|lacks?)\b")
    has_neg = any(neg.search(w) for w in windows)
    has_pos = any(not neg.search(w) for w in windows)
    expected = FC[named]
    j.check("answer_fc_status",
            (expected and has_pos and not has_neg) or ((not expected) and has_neg and not has_pos),
            f"final={fa[:300]!r} expected free_cancellation={expected} neg_mention={has_neg} pos_mention={has_pos}")
    j.emit()


if __name__ == "__main__":
    main()
