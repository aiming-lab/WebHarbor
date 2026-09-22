#!/usr/bin/env python3
"""Deterministic verifier for Apple task Apple--9.

Task: Check the Apple Store for the availability of the latest iPhone model and schedule an in-store pickup at the nearest Apple Store for January 10, 2024.

Ground truth (hardcoded; confirmed on the served mirror pages of the running
container — the catalog is fixed by the instance_seed DB, no wall-clock or
upstream content):
    /store/pickup?product=... lists Apple The Grove (0.8 miles), Apple
    Beverly Center (1.5 miles), Apple Century City (3.2 miles) — nearest is
    Apple The Grove — each "Available for pickup" with "Pickup Today:
    <product>". Scheduling for January 10, 2024 renders "Pickup scheduled …
    at Apple The Grove on 2024-01-10" (any date is accepted by the form).
    The latest iPhone models are the 17 series / iPhone Air slugs.
Checks: run-package gate + non-empty answer + read-only DB + navigation
(anti-shortcut) + answer facts.
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, step_urls, url_query, navigated_to,
                        navigated_any, navigated_path, navigated_paths_all,
                        visited_url_with, contains_all, contains_any,
                        contains_word, contains_words_any, price_in,
                        count_named, number_claim, is_jan10_2024, Judge,
                        parse_args)


def main():
    a = parse_args()
    j = Judge('Apple--9', a.no_llm)
    t, fa = grade_common(j, a)
    latest = ["iphone-17-pro", "iphone-17-pro-max", "iphone-17", "iphone-17e", "iphone-air"]
    nav_pickup = visited_url_with(t, "/store/pickup")
    j.check("nav_store_pickup", nav_pickup, "expected a /store/pickup URL")
    nav_product = any(visited_url_with(t, "/store/pickup", params_sub=[("product", s)])
                      for s in latest)
    j.check("nav_pickup_latest_iphone", nav_product,
            "pickup URL must carry a latest-iPhone (17 series / Air) product param")
    nav_store = visited_url_with(t, "/store/pickup", params_exact=[("store", "Apple The Grove")])
    j.check("nav_pickup_nearest_store", nav_store,
            "pickup URL must select Apple The Grove (nearest, 0.8 miles)")
    nav_date = False
    for u in step_urls(t):
        if "/store/pickup" in u.lower():
            q = url_query(u)
            if q.get("date") and is_jan10_2024(q["date"]):
                nav_date = True
    j.check("nav_pickup_jan10_2024", nav_date, "pickup URL must carry date=January 10, 2024")
    j.check("answer_mentions_grove", contains_any(fa, ["the grove"]), f"final={fa[:200]!r}")
    j.check("answer_mentions_jan10",
            contains_any(fa, ["january 10", "2024-01-10", "01/10/2024", "jan 10"]),
            f"final={fa[:200]!r}")
    j.check("answer_pickup_scheduled_available",
            contains_any(fa, ["pickup"]) and contains_any(fa, ["available", "in stock",
                                                              "pickup today", "scheduled"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
