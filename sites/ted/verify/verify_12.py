#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--12.

Log in as Alice and remove one saved talk that is NOT about AI. Seed baseline:
4 saved talks, exactly one about AI ('How I created OpenClaw, the breakthrough
AI agent'). A correct run removes one non-AI talk, leaving 3 with OpenClaw kept.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav /login,/account | DB after: exactly one talk removed, OpenClaw retained, removed talk is not the AI one
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
AI_MARKER = "openclaw"

def main():
    a = parse_args()
    j = Judge('TED--12', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    after_titles = saved_titles_for(after, EMAIL)
    init_titles = saved_titles_for(init, EMAIL)
    removed = ([] if (after_titles is None or init_titles is None)
               else [x for x in init_titles if norm(x) not in {norm(y) for y in after_titles}])
    j.check("nav_login", navigated_to(t, "/login"), f"navigated={navigated_to(t, '/login')}")
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    j.check("db_exactly_one_removed",
            after_titles is not None and init_titles is not None
            and len(after_titles) == len(init_titles) - 1,
            f"initial={init_titles} after={after_titles}")
    j.check("db_ai_talk_retained",
            after_titles is not None and any(AI_MARKER in norm(x) for x in after_titles),
            f"after={after_titles}")
    j.check("db_removed_not_ai",
            len(removed) == 1 and AI_MARKER not in norm(removed[0]), f"removed={removed}")
    j.emit()

if __name__ == "__main__":
    main()
