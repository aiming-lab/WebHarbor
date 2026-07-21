#!/usr/bin/env python3
"""Deterministic verifier for Target--1.

Open the ProsourceFit Extra Thick Yoga and Pilates Mat and report its material
and its length.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT91151386
  Material: Nitrile Butadiene Rubber
  Dimensions (Overall): 71 inches (L), 24.0 inches (W), 25.4 millimeter thick

The task used to ask for price and rating. Both are printed on the search
result card, so it was solvable without opening the product at all — a leak by
review-env's definition. Material and length appear only in the detail page's
specification table.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--1", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    SKU = "TGT91151386"
    j.check("opened_product_page", visited_product(t, SKU),
            f"visited /product/{SKU}={visited_product(t, SKU)}")
    j.check("answer_has_material",
            contains_any(fa, ["nitrile butadiene rubber", "nitrile butadiene", "nbr"]),
            f"final={fa!r}")
    j.check("answer_has_length", has_number(fa, 71), f"final={fa!r}")
    # Price/rating are card-level facts; quoting them instead of the spec means
    # the detail page was not actually read.
    j.check("not_card_level_answer_only",
            not (has_number(fa, 29.99) and not has_number(fa, 71)),
            f"answer looks like the search card only: final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Nitrile Butadiene Rubber; 71 inches long",
        "What material is the ProsourceFit yoga mat made of, and how long is it?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a specification table listing Nitrile Butadiene Rubber and 71 inches",
            "the yoga mat specification table")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
