#!/usr/bin/env python3
"""Deterministic verifier for Target--16.

Compare percent-recommended of Ninja DualBrew GP161 vs Cuisinart 14 Cup Programmable.

Ground truth (frozen here, never read from tasks.jsonl):
  Ninja DualBrew GP161 TGT94682442 = 66%; Cuisinart 14 Cup TGT94139349 = 59%.\n  Ninja is higher.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--16", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    NINJA, CUISINART = "TGT94682442", "TGT94139349"
    j.check("opened_ninja_page", visited_product(t, NINJA), f"visited={visited_product(t, NINJA)}")
    j.check("opened_cuisinart_page", visited_product(t, CUISINART),
            f"visited={visited_product(t, CUISINART)}")
    j.check("answer_has_both_percents", has_number(fa, 66) and has_number(fa, 59),
            f"final={fa!r}")
    j.check("answer_names_ninja_as_higher", contains_any(fa, ["ninja"]), f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Ninja DualBrew GP161 is higher at 66%, versus 59% for the Cuisinart 14 Cup", "Which coffee maker do more guests recommend, and what are both percentages?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "recommendation percentages 66% and 59%", "Which coffee maker do more guests recommend, and what are both percentages?")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
