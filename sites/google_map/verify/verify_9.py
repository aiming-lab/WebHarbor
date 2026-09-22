#!/usr/bin/env python3
"""Deterministic verifier for Google Map task Google Map--9.

Find the art gallery that is nearest to Los Angeles Hindu Temple.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    Los Angeles Hindu Temple (1600 Las Virgenes Canyon Rd, Calabasas) anchors
    the gallery search. The nearest art gallery is 'Las Virgenes Canyon Fine Art'
    (23501 Calabasas Rd, Calabasas, CA 91302, 4.6 stars, 0.4 mi from the temple).
    The runners-up: Malibu Creek Art Gallery (1.6 mi), Pacific Coast Contemporary
    (2.5 mi), Canyon Modern Art (3.4 mi), Westside Print & Paper Gallery (3.9 mi),
    Palisades Photography Gallery (6.8 mi).
    Source: the temple place page's 'Galleries nearby' section and
    /search?q=art+gallery+near+los+angeles+hindu+temple&sort=distance.

Checks (deterministic first; no LLM anywhere in this suite):
  nav: the temple page or an art-gallery search near it | answer names Las
  Virgenes Canyon Fine Art with nearest/closest evidence | read-only DB
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
    j = Judge('Google Map--9', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_temple_or_gallery_search",
            navigated_phrase(t, "hindu temple") or visited_place(t, "los-angeles-ca-los-angeles-hindu-temple")
            or navigated_phrase(t, "art gallery"),
            "temple place page or art-gallery search in the trajectory")
    j.check("answer_nearest_gallery", name_in(fa, "Las Virgenes Canyon Fine Art"),
            f"final={fa[:200]!r}")
    j.check("answer_nearest_evidence",
            contains_any(fa, ["0.4", "nearest", "closest"]),
            f"final={fa[:200]!r}")
    j.emit()

if __name__ == "__main__":
    main()
