#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--14.

Login alice + save serendipity; confirm on My Words page.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /login,/dictionary/serendipity,/account | DB after: serendipity in alice saved & not in initial seed | screenshot shows account page
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
    j = Judge('Merriam-Webster--14', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_login", navigated_to(t, "/login"), f"navigated={navigated_to(t, '/login')}")
    j.check("nav_serendipity_entry", navigated_to(t, "/dictionary/serendipity"),
            f"navigated={navigated_to(t, '/dictionary/serendipity')}")
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    aw = saved_words_for(after); iw = saved_words_for(init)
    j.check("db_serendipity_added", aw is not None and "serendipity" in (aw or []),
            f"after_saved={aw} initial_saved={iw}")
    j.check("db_serendipity_was_absent_initial", iw is not None and "serendipity" not in (iw or []),
            f"initial_saved={iw}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "serendipity", "the saved-words list on alice's account page")
        j.check("screenshot_shows_saved", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
