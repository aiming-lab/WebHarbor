#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--16.

Register 'Jordan Lee' + verify logged in.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /register | DB after: a user named 'Jordan Lee' exists | screenshot shows logged-in nav
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, last_shot, shot_after_url,
                        contains_all, contains_any, answer_equals, extract_years,
                        extract_score, resolve_db, saved_words_for, user_exists,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('Merriam-Webster--16', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_register", navigated_to(t, "/register"), f"navigated={navigated_to(t, '/register')}")
    after = resolve_db(a.after_db, a.container, "instance")
    exists = user_exists(after, name="Jordan Lee")
    j.check("db_jordan_lee_registered", exists is True, f"user_exists_Jordan_Lee={exists}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "My Words", "navigation showing the user is logged in (My Words / Log Out)")
        j.check("screenshot_shows_logged_in", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
