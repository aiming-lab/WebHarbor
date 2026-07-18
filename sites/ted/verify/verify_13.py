#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--13.

Find the science topic page and identify the TEDx talk specifically about wine
tasting. -> Qian Janice Wang, 'The art and science of wine tasting'.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav Qian Janice Wang talk detail | answer names the wine-tasting talk / speaker
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "qian-janice-wang-the-art-and-science-of-wine-tasting"

def main():
    a = parse_args()
    j = Judge('TED--13', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_wine_talk", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_wine_talk",
            contains_any(fa, ["Qian Janice Wang", "The art and science of wine tasting"]),
            f"final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
