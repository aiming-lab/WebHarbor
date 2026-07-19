#!/usr/bin/env python3
"""Deterministic verifier for WebMD--15.

Register a new account (name Jordan Rivera, email jordan.rivera@example.com,
password DemoPass789!), open account settings, confirm the profile name.
Ground truth (after-state): a user row with that name+email exists; it must NOT
exist in the initial seed (registration actually happened).

Checks: nav /register | DB after: Jordan Rivera exists & absent from seed | answer confirms name | LLM+screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        shot_after_url, contains_all, contains_any, answer_equals,
                        date_present, resolve_db, saved_slugs_for, saved_count_for,
                        user_exists, password_hash_for, password_matches,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

NAME = "Jordan Rivera"
EMAIL = "jordan.rivera@example.com"

def main():
    a = parse_args()
    j = Judge('WebMD--15', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_register", navigated_to(t, "/register"),
            f"navigated={navigated_to(t, '/register')}")
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    exists_after = user_exists(after, name=NAME, email=EMAIL)
    exists_init = user_exists(init, email=EMAIL)
    j.check("db_user_registered", exists_after is True, f"after_exists={exists_after}")
    j.check("db_user_absent_in_seed", exists_init is False, f"seed_exists={exists_init}")
    j.check("answer_confirms_name", contains_any(fa, ["jordan rivera"]), f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Jordan Rivera",
            "the account/profile page showing the newly registered name")
        j.check("screenshot_shows_name", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
