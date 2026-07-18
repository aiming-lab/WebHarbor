#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--15.

Among the music-topic talks by Akoth Jumadi and Mr. Lu vs Turkana Sessions,
which has more views? -> Turkana Sessions (4,223 views vs 2,781).

Checks (deterministic first; LLM utilities anchored on ground truth):
nav both talk details | answer names Turkana Sessions as having more views
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

AKOTH = "akoth-jumadi-and-mr-lu-east-african-sound-meets-cosmic-trap"
TURKANA = "turkana-sessions-a-musical-journey-through-turkana"

def main():
    a = parse_args()
    j = Judge('TED--15', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_akoth", navigated_to(t, AKOTH), f"navigated={navigated_to(t, AKOTH)}")
    j.check("nav_turkana", navigated_to(t, TURKANA), f"navigated={navigated_to(t, TURKANA)}")
    j.check("answer_turkana_more",
            contains_any(fa, ["Turkana Sessions", "A musical journey through Turkana"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Turkana Sessions ('A musical journey through Turkana') has more views",
        "Which talk has more views: Akoth Jumadi and Mr. Lu, or Turkana Sessions?")
    j.check("answer_more_views_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
