#!/usr/bin/env python3
"""Deterministic verifier for Target--2.

In the Grocery department, find Katie's Burrata Margherita Frozen Pizza and
report the sodium per serving.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT94764181, Nutrition Facts -> Sodium 610mg

Checks: opened THIS product's detail page | answer states 610 mg | read-only
run left the DB untouched | screenshot visibly shows the nutrition row.
The sodium row exists only on the detail page — it is not on a search card —
so a correct answer without the navigation step is a knowledge shortcut.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product,
                        has_number, contains_any, resolve_db, db_unchanged_for,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

SKU = "TGT94764181"
SODIUM_MG = 610


def main():
    a = parse_args()
    j = Judge("Target--2", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_product_page", visited_product(t, SKU),
            f"visited /product/{SKU}={visited_product(t, SKU)}")

    # 610 must appear as a number, and the answer must be about sodium/mg —
    # "610" alone could be a price or a SKU fragment.
    j.check("answer_sodium_value", has_number(fa, SODIUM_MG), f"final={fa!r}")
    j.check("answer_mentions_sodium", contains_any(fa, ["sodium", "mg"]),
            f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"cart/wishlist/orders unchanged={unchanged}")

    ok, ev = llm_text_match(fa, f"{SODIUM_MG}mg of sodium per serving",
        "How much sodium per serving does Katie's Burrata Margherita Frozen Pizza contain?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"Sodium {SODIUM_MG}mg",
            "the sodium row in the product's nutrition facts")
        j.check("screenshot_shows_sodium", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_sodium", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
