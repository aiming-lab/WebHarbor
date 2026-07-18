#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--10.

Open the 'AI, Society, and the Future' playlist; which included talk discusses a
Supreme Court case? -> Neal Kumar Katyal, 'What really won the trillion-dollar
Supreme Court case'.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav ai-and-society playlist | answer names Neal Katyal / the Supreme Court talk
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
    j = Judge('TED--10', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_ai_society", navigated_to(t, "playlists/ai-and-society"),
            f"navigated={navigated_to(t, 'playlists/ai-and-society')}")
    j.check("answer_supreme_court_talk",
            contains_any(fa, ["Neal Kumar Katyal", "Neal Katyal",
                              "What really won the trillion-dollar Supreme Court case"]),
            f"final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
