#!/usr/bin/env python3
"""Deterministic verifier for Booking task Booking--35.

Browse the booking website for trip inspiration and summarize at least three
places mentioned in one of the travel articles.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    The site has a travel-articles section (/articles) with 7 articles, each
    listing the places it covers. The article pages (not the homepage cards)
    carry the place details; the verifier grades the places of the article the
    run actually opened.

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

ARTICLES = {
    "top-5-european-cities-food-lovers": [
        "Paris",
        "Rome",
        "Lisbon",
        "Barcelona",
        "Vienna"
    ],
    "asia-on-a-budget": [
        "Bali",
        "Bangkok",
        "Singapore"
    ],
    "romantic-city-breaks": [
        "Paris",
        "Rome",
        "Vienna",
        "Amsterdam"
    ],
    "beach-getaways-winter-sun": [
        "Bali",
        "Maldives",
        "Lisbon"
    ],
    "family-friendly-city-holidays": [
        "London",
        "Amsterdam",
        "Barcelona",
        "Singapore"
    ],
    "slow-travel-japan": [
        "Tokyo",
        "Sapporo",
        "Osaka"
    ],
    "landmark-hotels-with-a-view": [
        "London",
        "Dubai",
        "Singapore",
        "New York",
        "Hong Kong"
    ]
}


def main():
    a = parse_args()
    j = Judge('Booking--35', a.no_llm)
    t, fa = grade_common(j, a)
    opened = [slug for slug in ARTICLES if navigated_to(t, f"/articles/{slug}")]
    j.check("nav_article_page", bool(opened),
            f"urls={[u for u in step_urls(t) if '/articles/' in u][:4]} an article page must be opened")
    if not opened:
        j.emit()
    best = 0
    for slug in opened:
        hits = sum(1 for pl in ARTICLES[slug] if norm(pl) in norm(fa))
        best = max(best, hits)
    j.check("answer_three_places", best >= 3,
            f"final={fa[:300]!r} places_from_opened_article={best}")
    j.emit()


if __name__ == "__main__":
    main()
