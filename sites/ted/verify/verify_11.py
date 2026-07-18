#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--11.

Use the filters to find TED2026 talks under 10 minutes and open the talk by
Maya Higa. This is a navigation task (no factual answer required).

Checks (deterministic first; LLM utilities anchored on ground truth):
nav filtered /talks listing | nav Maya Higa talk detail
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "maya-higa-the-wildlife-sanctuary-you-can-visit-from-anywhere"

def main():
    a = parse_args()
    j = Judge('TED--11', a.no_llm)
    t = load_run(a.run_dir)
    # Require the filtered listing specifically: "/talks?" (a query string) is
    # only produced by the GET filter form, whereas "/talks" alone would also
    # match every "/talks/<slug>" detail page and make this check vacuous.
    j.check("nav_talks_listing", navigated_to(t, "/talks?"), f"navigated={navigated_to(t, '/talks?')}")
    j.check("nav_maya_higa", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.emit()

if __name__ == "__main__":
    main()
