#!/usr/bin/env python3
"""Deterministic verifier for MW task Merriam-Webster--10.

WOTD ephemeral; Did You Know? etymology text.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /word-of-the-day/ephemeral | answer contains 'greek ephēmeros' (deterministic) | screenshot shows Did You Know
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
    j = Judge('Merriam-Webster--10', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_wotd_ephemeral", navigated_to(t, "/word-of-the-day/ephemeral"),
            f"navigated={navigated_to(t, '/word-of-the-day/ephemeral')}")
    j.check("answer_did_you_know", contains_any(fa, ["greek eph\u0113meros", "ephemeros lasting a day"]),
            f"final={fa!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Greek eph\u0113meros", "Did You Know section of the ephemeral WOTD entry")
        j.check("screenshot_shows_dyk", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
