#!/usr/bin/env python3
"""Deterministic verifier for Target--13.

Find the Denver store and report its address and a pickup service.

Ground truth (frozen here, never read from tasks.jsonl):
  Store 'denver-stapleton', address 7400 E 29th Ave.\n  Amenities: Curbside pickup, Gift wrapping, Mobile checkout.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--13", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_store_page", navigated_to(t, "/stores/denver-stapleton"),
            f"visited={navigated_to(t, '/stores/denver-stapleton')}")
    j.check("answer_has_address", contains_all(fa, ["7400", "29th"]), f"final={fa!r}")
    j.check("answer_has_a_service",
            contains_any(fa, ["curbside", "gift wrapping", "mobile checkout", "pickup"]),
            f"final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "Denver Stapleton, 7400 E 29th Ave, offering Curbside pickup", "What is the Denver store's address and a pickup service it offers?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the store address 7400 E 29th Ave", "What is the Denver store's address and a pickup service it offers?")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
