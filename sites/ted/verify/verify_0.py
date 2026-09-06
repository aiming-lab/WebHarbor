#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--0.

Search for AI talks, open Anil Seth's talk, report its duration in minutes.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav Anil Seth talk detail | answer duration == 15 minutes | screenshot shows duration
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "anil-seth-why-ai-is-unlikely-to-become-conscious"

def main():
    a = parse_args()
    j = Judge('TED--0', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_anil_seth", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_duration_15", 15 in extract_ints(fa), f"final={fa!r} ints={extract_ints(fa)}")
    ok, ev = llm_text_match(fa, "15 minutes",
        "What is the duration in minutes of Anil Seth's talk 'Why AI is unlikely to become conscious'?")
    j.check("answer_duration_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
