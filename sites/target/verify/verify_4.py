#!/usr/bin/env python3
"""Deterministic verifier for Target--4.

Report Mr. Coffee 5 Cup Switch percent-recommended and its highest-scoring attribute.

Ground truth (frozen here, never read from tasks.jsonl):
  SKU TGT91986267, 74% would recommend.\n  Secondary ratings: quality 4.1, design 4.2, ease of use 4.5, easy to clean 4.6, value 4.3\n  -> highest is 'easy to clean' (4.6).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--4", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    SKU = "TGT91986267"
    j.check("opened_product_page", visited_product(t, SKU),
            f"visited={visited_product(t, SKU)}")
    j.check("answer_has_percent", has_number(fa, 74), f"final={fa!r}")
    j.check("answer_names_easy_to_clean", contains_any(fa, ["easy to clean", "easy-to-clean"]),
            f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "74% would recommend; the highest rated attribute is 'easy to clean' at 4.6 out of 5", "What percent of guests recommend the Mr. Coffee 5 Cup Switch, and which attribute scored highest?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "74% would recommend and an easy to clean rating", "What percent of guests recommend the Mr. Coffee 5 Cup Switch, and which attribute scored highest?")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
