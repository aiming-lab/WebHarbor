#!/usr/bin/env python3
"""Deterministic verifier for Target--5.

Report the price gap between the Sony WH-1000XM6 3-year and 2-year protection plans, and which covers accidental handling.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT94760871. 2-year $36.72 (no accidental), 3-year $59.67 (accidental).\n  Difference = $22.95; the 3-year plan covers accidental handling.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--5", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    SKU = "TGT94760871"
    j.check("opened_product_page", visited_product(t, SKU),
            f"visited={visited_product(t, SKU)}")
    # Accept either the delta or both plan prices stated.
    delta_ok = has_number(fa, 22.95)
    both_ok = has_number(fa, 36.72) and has_number(fa, 59.67)
    j.check("answer_has_price_gap", delta_ok or both_ok,
            f"delta={delta_ok} both_prices={both_ok} final={fa!r}")
    j.check("answer_names_three_year_plan", contains_any(fa, ["3-year", "3 year", "three-year", "three year"]),
            f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "The 3-year plan costs $22.95 more ($59.67 vs $36.72) and it is the plan that covers accidental handling", "How much more is the 3-year protection plan than the 2-year, and which covers accidental handling?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "two protection plan prices", "How much more is the 3-year protection plan than the 2-year, and which covers accidental handling?")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
