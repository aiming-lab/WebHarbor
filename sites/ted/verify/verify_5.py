#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--5.

Find Malala Yousafzai's talk and report its exact title. (Re-anchored from the
original 'list two topics', which a model could answer from prior knowledge; the
title is on-page only — listing cards show the speaker, not the title.)

Checks (deterministic first; LLM utilities anchored on ground truth):
nav Malala talk detail | answer contains the exact title
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "malala-yousafzai-what-i-got-wrong-about-changing-the-world"
TITLE = "What I got wrong about changing the world"

def main():
    a = parse_args()
    j = Judge('TED--5', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_malala", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_exact_title", contains_all(fa, [TITLE]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, TITLE, "What is the exact title of Malala Yousafzai's talk?")
    j.check("answer_title_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
