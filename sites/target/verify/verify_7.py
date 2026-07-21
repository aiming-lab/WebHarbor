#!/usr/bin/env python3
"""Deterministic verifier for Target--7.

Compare Red Baron Supreme Classic Crust vs Pepperoni Deep Dish Personal by sodium.

Ground truth (frozen here, never read from tasks.jsonl):
  Supreme Classic TGT13333997 = 650mg; Pepperoni Deep Dish Personal TGT13374157 = 1950mg.\n  Supreme has less, by 1300mg.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--7", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    SUPREME, DEEPDISH = "TGT13333997", "TGT13374157"
    j.check("opened_supreme_page", visited_product(t, SUPREME),
            f"visited={visited_product(t, SUPREME)}")
    j.check("opened_deepdish_page", visited_product(t, DEEPDISH),
            f"visited={visited_product(t, DEEPDISH)}")
    j.check("answer_names_supreme_as_lower", contains_any(fa, ["supreme"]), f"final={fa!r}")
    # Either the difference or both raw values proves the arithmetic was done.
    diff_ok = has_number(fa, 1300)
    both_ok = has_number(fa, 650) and has_number(fa, 1950)
    j.check("answer_has_difference", diff_ok or both_ok,
            f"diff={diff_ok} both={both_ok} final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Red Baron Supreme Classic Crust has less sodium: 650mg vs 1950mg, a difference of 1300mg", "Which pizza has less sodium and by how many milligrams?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "sodium values 650mg and 1950mg", "Which pizza has less sodium and by how many milligrams?")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
