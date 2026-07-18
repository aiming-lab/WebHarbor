#!/usr/bin/env python3
"""Deterministic verifier for TED task TED--9.

Find a talk about Parkinson's and save it to Alice's account with a note for
public health review. Ground truth: Joy Milne, 'The nurse who can smell
Parkinson's'.

Checks (deterministic first; LLM utilities anchored on ground truth):
nav Joy Milne talk detail + /login | DB after: talk saved by alice with a non-empty note, absent in seed
Input/Output: see verify_lib.parse_args / Judge.emit.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        norm, contains_all, contains_any, answer_equals, extract_ints,
                        resolve_db, saved_talks_for, saved_titles_for, note_for_saved,
                        newsletter_topic_for, registered_events_for, user_emails,
                        SEED_EMAILS, llm_text_match, llm_screenshot_shows, Judge, parse_args)

SLUG = "joy-milne-the-nurse-who-can-smell-parkinson-s"
TITLE_SUB = "smell Parkinson"
EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge('TED--9', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    note = note_for_saved(after, EMAIL, TITLE_SUB)
    init_titles = saved_titles_for(init)
    j.check("nav_parkinson", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("db_parkinson_saved_by_alice", note is not None, f"note={note!r}")
    j.check("db_note_present", bool(note and note.strip()), f"note={note!r}")
    j.check("db_absent_in_seed",
            init_titles is not None and not any(norm(TITLE_SUB) in norm(x) for x in init_titles),
            f"initial_saved={init_titles}")
    # The note text is free-form; confirm it reads as a public-health review note (anchored).
    ok, ev = llm_text_match(note or "", "a note about public health / public health review",
        "Is this saved-talk note a note for public health review?")
    j.check("note_public_health_llm", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
