#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--7.

Register interest in the TED2026 event while logged in as Alice. (Re-anchored
from 'TED Countdown Summit 2025', which Alice is already seed-registered for —
that made the task a no-op and the after-state indistinguishable from doing
nothing. Alice is NOT seed-registered for TED2026, so a registration is a
genuine, verifiable state change.)

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /events + /login | DB after: alice registered for TED2026, not registered in seed
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
EVENT = "TED2026"

def main():
    a = parse_args()
    j = Judge('TED--7', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after_regs = registered_events_for(after, EMAIL)
    init_regs = registered_events_for(init, EMAIL)
    j.check("nav_events", navigated_to(t, "/events"), f"navigated={navigated_to(t, '/events')}")
    j.check("nav_login", navigated_to(t, "/login"), f"navigated={navigated_to(t, '/login')}")
    j.check("db_registered_ted2026",
            after_regs is not None and EVENT in after_regs, f"after_regs={after_regs}")
    j.check("db_not_registered_in_seed",
            init_regs is not None and EVENT not in init_regs, f"initial_regs={init_regs}")
    j.emit()

if __name__ == "__main__":
    main()
