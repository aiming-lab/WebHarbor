#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--17.

Open events and identify the month scheduled for the TEDNext 2025 event.
-> November 2025. (Re-anchored from the original 'city', which was Atlanta — a
value that matches the real world and is answerable from prior knowledge. The
month is a mirror-specific synthetic field, so it is only obtainable on-page.)

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /events | answer names the month 'November' (2025)
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('TED--17', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_events", navigated_to(t, "/events"), f"navigated={navigated_to(t, '/events')}")
    j.check("answer_month_november", contains_all(fa, ["november"]), f"final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
