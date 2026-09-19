#!/usr/bin/env python3
"""Deterministic verifier for Amazon task Amazon--12.

Check reviews for a Ride On Car with 100+ reviews & 4+ stars rating on Amazon. Give me the top review about this Ride On Car.

Ground truth (hardcoded; confirmed by browsing the served mirror pages — the
catalog is fixed by the seed DB, no wall-clock or upstream content involved):
    Qualifying ride-ons (100+ displayed reviews, >=4 stars) and the Top Review
    highlighted on each product page (highest rating, then most recent):
    Best Choice Products 12V Kids Licensed Ride On Car (12,543, 4.4) ->
    'Best Ride-On We've Owned'; BCP 12V Kids Ride On Truck (3,200, 4.5) ->
    'Amazing ride-on truck, kids love it!'; Power Wheels Barbie Jeep (8,400,
    4.6) -> 'Daughter is thrilled with her Barbie Jeep'; Peg Perego John Deere
    Ground Force Tractor (4,500, 4.7) -> 'Solid value'; Mercedes-Benz G63 AMG
    (512, 4.1) and Lamborghini Aventador (1,280, 4.6) -> 'Perfect for my 4 year
    old'. The answer must quote the top review of a qualifying product whose
    page the run actually opened.

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
    j = Judge('Amazon--12', a.no_llm)
    t, fa = grade_common(j, a)
    urls = __import__('verify_lib').step_urls(t)
    RIDEONS = [
        ("best-choice-products-12v-kids-licensed-ride-on-car", ["best choice", "licensed ride on car"],
         ["best ride-on we", "we've owned", "we’ve owned"]),
        ("best-choice-products-12v-kids-ride-on-truck", ["ride on truck"],
         ["amazing ride-on truck"]),
        ("power-wheels-barbie-jeep-wrangler-12v-ride-on", ["barbie jeep"],
         ["daughter is thrilled"]),
        ("peg-perego-john-deere-ground-force-tractor", ["john deere"],
         ["solid value"]),
        ("mercedes-benz-g63-amg-12v-kids-ride-on-car", ["mercedes"],
         ["perfect for my 4 year old"]),
        ("lamborghini-aventador-12v-kids-ride-on-sports-car", ["lamborghini"],
         ["perfect for my 4 year old"]),
    ]
    j.check("nav_ride_on", navigated_to(t, "ride on") or navigated_to(t, "ride-on"),
            f"urls={[u for u in urls if 'ride' in u.lower()][:4]}")
    visited = [r for r in RIDEONS if visited_product(t, r[0])]
    j.check("nav_qualifying_product_page", bool(visited),
            f"visited={[v[0] for v in visited]}")
    j.check("answer_names_visited_product",
            any(contains_any(fa, v[1]) for v in visited) if visited else False,
            "the reported ride-on is one whose page was opened")
    j.check("answer_top_review_of_visited_product",
            any(contains_any(fa, v[2]) for v in visited) if visited else False,
            "top-review title of the visited qualifying ride-on quoted")
    j.emit()


if __name__ == "__main__":
    main()
