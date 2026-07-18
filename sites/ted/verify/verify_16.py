#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--16.

Create a new account, save Peter Steinberger's AI-agent talk ('How I created
OpenClaw, the breakthrough AI agent'), then confirm it appears under saved talks.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /register + Peter Steinberger talk detail + /account | DB after: a NON-seed user exists with the OpenClaw talk saved
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "peter-steinberger-how-i-created-openclaw-the-breakthrough-ai-agent"
OPENCLAW = "openclaw"

def main():
    a = parse_args()
    j = Judge('TED--16', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    emails = user_emails(after)
    new_emails = [e for e in (emails or []) if e not in SEED_EMAILS]
    saved_by_new = False
    for e in new_emails:
        titles = saved_titles_for(after, e) or []
        if any(OPENCLAW in norm(x) for x in titles):
            saved_by_new = True
            break
    j.check("nav_register", navigated_to(t, "/register"), f"navigated={navigated_to(t, '/register')}")
    j.check("nav_openclaw_talk", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    j.check("db_new_user_created", bool(new_emails), f"non_seed_users={new_emails}")
    j.check("db_new_user_saved_openclaw", saved_by_new, f"non_seed_users={new_emails}")
    j.emit()

if __name__ == "__main__":
    main()
