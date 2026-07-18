#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--8.

Compare Alexi Pappas's 'Why I love my bad days' (5 min) with Debbie Millman's
'You got what you wanted. Now what?' (8 min) — which is shorter? -> Alexi Pappas.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav both talk details | answer names Alexi Pappas / 'Why I love my bad days' as shorter
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

ALEXI = "alexi-pappas-why-i-love-my-bad-days"
DEBBIE = "debbie-millman-you-got-what-you-wanted-now-what"

def main():
    a = parse_args()
    j = Judge('TED--8', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_alexi", navigated_to(t, ALEXI), f"navigated={navigated_to(t, ALEXI)}")
    j.check("nav_debbie", navigated_to(t, DEBBIE), f"navigated={navigated_to(t, DEBBIE)}")
    j.check("answer_alexi_shorter",
            contains_any(fa, ["Alexi Pappas", "Why I love my bad days"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Alexi Pappas's 'Why I love my bad days' (5 minutes) is the shorter talk",
        "Which talk is shorter: Alexi Pappas's 'Why I love my bad days' or Debbie Millman's "
        "'You got what you wanted. Now what?'")
    j.check("answer_shorter_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
