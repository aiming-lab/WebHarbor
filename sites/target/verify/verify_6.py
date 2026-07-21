#!/usr/bin/env python3
"""Deterministic verifier for Target--6 (search & filter).

Browse Pets, filter to pickup-eligible items, sort price low to high, and
report the name and price of the first result.

Ground truth (frozen here, never read from tasks.jsonl):
  Cheapest pickup-eligible product in Pets = Wet Dog Food - 12.5oz - Kindfull
  (SKU TGT82688642) at $2.19.

The check requires the filtered listing URL, not just any Pets page: the
answer is only correct under BOTH the pickup filter and the price sort, so
an agent that eyeballed the unsorted first page should not pass.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, step_urls,
                        navigated_to, has_number, contains_any, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)

PRICE = 2.19


def main():
    a = parse_args()
    j = Judge("Target--6", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("browsed_pets_category", navigated_to(t, "/category/pets"),
            f"visited={navigated_to(t, '/category/pets')}")

    urls = [u.lower() for u in step_urls(t)]
    applied = any("pickup=1" in u or "availability=pickup" in u for u in urls)
    sorted_ = any("sort=price-asc" in u for u in urls)
    j.check("applied_pickup_filter", applied,
            f"no pickup filter in any URL: {urls[:6]}")
    j.check("applied_price_sort", sorted_,
            f"no sort=price-asc in any URL: {urls[:6]}")

    j.check("answer_has_price", has_number(fa, PRICE), f"final={fa!r}")
    j.check("answer_names_product", contains_any(fa, ["wet dog food", "kindfull"]),
            f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Wet Dog Food - 12.5oz - Kindfull, $2.19",
        "What is the cheapest pickup-eligible product in the Pets department?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a Pets listing sorted by price with a $2.19 item first",
                                      "the filtered and sorted Pets listing")
        j.check("screenshot_shows_listing", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_listing", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
