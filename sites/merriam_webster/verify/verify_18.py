#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--18.

Login alice + remove 'curiosity'; confirm list == harmony, eloquent.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /login,/account | DB after: alice saved words exactly [eloquent, harmony] (no curiosity) | screenshot shows account page
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
    j = Judge('Merriam-Webster--18', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_login", navigated_to(t, "/login"), f"navigated={navigated_to(t, '/login')}")
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    after = resolve_db(a.after_db, a.container, "instance")
    aw = saved_words_for(after)
    j.check("db_curiosity_removed", aw is not None and "curiosity" not in (aw or []), f"after_saved={aw}")
    j.check("db_list_exactly_2", aw is not None and sorted(aw or []) == ["eloquent", "harmony"], f"after_saved={aw}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "harmony", "saved-words list showing only harmony and eloquent")
        j.check("screenshot_shows_list", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
