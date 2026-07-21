#!/usr/bin/env python3
"""Deterministic verifier for Target--3.

Compare sodium of Red Baron Pepperoni Classic Crust vs Four Cheese Classic Crust.

Ground truth (frozen here, never read from tasks.jsonl):
  Pepperoni Classic TGT13376389 = 790mg; Four Cheese Classic TGT13334000 = 710mg.\n  Four Cheese has LESS sodium.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--3", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    PEPPERONI, FOURCHEESE = "TGT13376389", "TGT13334000"
    j.check("opened_pepperoni_page", visited_product(t, PEPPERONI),
            f"visited={visited_product(t, PEPPERONI)}")
    j.check("opened_fourcheese_page", visited_product(t, FOURCHEESE),
            f"visited={visited_product(t, FOURCHEESE)}")
    j.check("answer_has_both_values", has_number(fa, 790) and has_number(fa, 710),
            f"final={fa!r}")
    # The comparison itself must be right, not just the two numbers quoted.
    j.check("answer_names_four_cheese_as_lower", contains_any(fa, ["four cheese", "4 cheese"]),
            f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Four Cheese Classic Crust has less sodium: 710mg vs 790mg for Pepperoni Classic Crust", "Which of the two Red Baron Classic Crust pizzas has less sodium, and what are the values?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "sodium values 790mg and 710mg", "Which of the two Red Baron Classic Crust pizzas has less sodium, and what are the values?")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
