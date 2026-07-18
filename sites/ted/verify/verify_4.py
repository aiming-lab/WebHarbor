#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--4.

Log in as Alice and change the newsletter topic to conservation.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /login,/account | DB after: alice newsletter_topic == 'conservation' (seed was 'ai')
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge('TED--4', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    topic = newsletter_topic_for(after, EMAIL)
    j.check("nav_login", navigated_to(t, "/login"), f"navigated={navigated_to(t, '/login')}")
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    j.check("db_newsletter_conservation", topic is not None and norm(topic) == "conservation",
            f"newsletter_topic={topic!r}")
    j.emit()

if __name__ == "__main__":
    main()
