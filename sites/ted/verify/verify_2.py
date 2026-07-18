#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--2.

Browse the design topic, open Debbie Millman's TEDNext 2025 talk shorter than
10 minutes, report its duration in minutes.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav Debbie Millman 'You got what you wanted' detail | answer duration == 8 minutes
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "debbie-millman-you-got-what-you-wanted-now-what"

def main():
    a = parse_args()
    j = Judge('TED--2', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_debbie_millman", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_duration_8", 8 in extract_ints(fa), f"final={fa!r} ints={extract_ints(fa)}")
    ok, ev = llm_text_match(fa, "8 minutes",
        "What is the duration in minutes of Debbie Millman's talk 'You got what you wanted. Now what?'")
    j.check("answer_duration_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
