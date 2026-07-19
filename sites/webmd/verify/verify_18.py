#!/usr/bin/env python3
"""Deterministic verifier for WebMD--18.

Log in as carol.w@test.com, open Saved Articles, report how many are saved.
Ground truth: carol has 4 saved articles in the seed. The count is verified
against the DB so it stays correct even if the seed distribution changes.

Checks: nav login + saved | answer matches DB saved-count | LLM+screenshot anchored.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        shot_after_url, contains_all, contains_any, contains_number,
                        answer_equals, date_present, resolve_db, saved_slugs_for,
                        saved_count_for, user_exists, password_hash_for, password_matches,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

EMAIL = "carol.w@test.com"

def main():
    a = parse_args()
    j = Judge('WebMD--18', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_login", navigated_to(t, "/login"), f"navigated={navigated_to(t, '/login')}")
    j.check("nav_saved", navigated_to(t, "/account/saved"),
            f"navigated={navigated_to(t, '/account/saved')}")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    count = saved_count_for(init, EMAIL)
    # Fail closed if the DB is unavailable — never grade against a hard-coded guess.
    j.check("db_available", count is not None, f"saved_count={count}")
    j.check("answer_matches_saved_count", count is not None and contains_number(fa, count),
            f"expected={count} final={fa!r}")
    ok, ev = llm_text_match(fa, f"{count} saved articles",
        "How many articles are in carol.w@test.com's saved-articles list?")
    j.check("answer_count_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/account/saved") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"a saved-articles list containing {count} items",
            "carol's Saved Articles page")
        j.check("screenshot_shows_saved_list", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
