#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--14.

Search 'architecture 3D printing', open the talk about traditional architecture,
report the speaker. -> Riyad Joucka ('Reimagining traditional architecture for
modern needs'). Kate Canales's makeshift-signs talk is the near-miss distractor.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav Riyad Joucka talk detail | answer names the speaker Riyad Joucka
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "riyad-joucka-reimagining-traditional-architecture-for-modern-needs"

def main():
    a = parse_args()
    j = Judge('TED--14', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_riyad", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("answer_speaker", contains_all(fa, ["Riyad Joucka"]), f"final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
