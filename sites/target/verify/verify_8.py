#!/usr/bin/env python3
"""Deterministic verifier for Target--8.

Sign in as david.k and report the order number and total of the Processing order.

Ground truth (frozen here, never read from tasks.jsonl):
  david.k@test.com has exactly one Processing order: TGT-240013, total $32.61.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--8", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_order_history", navigated_to(t, "/account/orders"),
            f"visited={navigated_to(t, '/account/orders')}")
    j.check("answer_has_order_number", contains_any(fa, ["TGT-240013"]), f"final={fa!r}")
    j.check("answer_has_total", has_number(fa, 32.61), f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "david.k@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Order TGT-240013, total $32.61", "Which order is still Processing, and what is its total?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "order TGT-240013 with a $32.61 total", "Which order is still Processing, and what is its total?")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
