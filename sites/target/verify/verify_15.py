#!/usr/bin/env python3
"""Deterministic verifier for Target--15 (multi-page comparison).

Across the Red Baron frozen pizzas, report which has the LOWEST sodium per
serving and what that value is.

Ground truth (frozen here, never read from tasks.jsonl):
  Red Baron Supreme Classic Crust        650mg   <- lowest, unique
  Red Baron Four Cheese Classic Crust    710mg
  Red Baron Cheese Trio Brick Oven       710mg
  Red Baron Pepperoni Classic Crust      790mg
  Red Baron Pepperoni Brick Oven         810mg
  Red Baron Four Cheese Deep Dish        1750mg
  Red Baron Pepperoni Deep Dish          1950mg

650mg is held by exactly one product, so the answer is unambiguous. Sodium is
absent from every listing page, so the values can only come from the detail
pages — requiring more than one visit is what makes this a comparison rather
than a lookup.

An earlier version of this task asked for "the sodium of the Red Baron frozen
pizza" and graded on whether the agent asked which one. CONTRIBUTING rejects
tasks that presuppose a human in the loop, so it was re-anchored onto a
question with a single correct answer.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, step_urls,
                        has_number, contains_any, resolve_db, db_unchanged_for,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

LOWEST_MG = 650
OTHER_VALUES = [710, 790, 810, 1750, 1950]
# Every Red Baron SKU, so we can count how many detail pages were opened.
RED_BARON_SKUS = ["TGT13333997", "TGT13334000", "TGT31168521", "TGT13376389",
                  "TGT31168522", "TGT13374348", "TGT13374157"]


def main():
    a = parse_args()
    j = Judge("Target--15", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    urls = " ".join(step_urls(t))
    opened = [s for s in RED_BARON_SKUS if f"/product/{s}" in urls]
    # One page cannot establish a minimum across the range.
    j.check("opened_multiple_product_pages", len(opened) >= 2,
            f"opened {len(opened)} Red Baron product pages: {opened}")

    j.check("answer_has_lowest_value", has_number(fa, LOWEST_MG), f"final={fa!r}")
    j.check("answer_names_supreme", contains_any(fa, ["supreme"]), f"final={fa!r}")
    # Quoting a different variant's figure as "the lowest" is the wrong answer.
    wrong = [v for v in OTHER_VALUES if has_number(fa, v)
             and not has_number(fa, LOWEST_MG)]
    j.check("did_not_report_a_higher_variant", not wrong,
            f"answer quotes {wrong} but not {LOWEST_MG}: final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Red Baron Supreme Classic Crust, 650mg of sodium per serving",
        "Which Red Baron frozen pizza has the lowest sodium per serving, and what is that value?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a Red Baron pizza nutrition row showing 650mg of sodium",
                                      "the lowest-sodium Red Baron pizza's nutrition facts")
        j.check("screenshot_shows_sodium", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_sodium", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
