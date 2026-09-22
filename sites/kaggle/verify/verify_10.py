#!/usr/bin/env python3
"""Verifier for Kaggle--10 (stateful).

Sign in as alice.j@test.com and start a new discussion in the 'Questions & Answers' forum
titled 'How do you handle class imbalance?' with a short body. Ground truth (after-state):
a discussions row authored by alice's username (alicejdata) with that title, forum
'Questions & Answers'. No such thread in seed -> no-op FAILs.

Checks: nav login + new-discussion | DB after: discussion row (author, title, forum).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, db_query, discussion_row, last_shot, llm_screenshot_shows,
                        load_run, navigated_to, norm, origin_ok, parse_args, resolve_db,
                        run_complete, shot_at, shot_distinct, shot_final)

USERNAME = "alicejdata"
TITLE_SUBSTR = "how do you handle class imbalance"
TITLE = "how do you handle class imbalance?"

def main():
    a = parse_args()
    j = Judge('Kaggle--10', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_new_discussion", navigated_to(t, "/discussions/new"), "opened the new-discussion form")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    row = discussion_row(after, USERNAME, TITLE_SUBSTR) if after else None
    before_row = discussion_row(init, USERNAME, TITLE_SUBSTR) if init else None
    j.check("db_discussion_created", before_row is None and row is not None,
            f"seed={before_row!r} after={row!r}")
    j.check("db_title_exact", row is not None and norm(row[0]) == TITLE,
            f"title={row[0] if row else None!r}")
    j.check("db_forum_qa", row is not None and norm(row[1]) == "questions & answers",
            f"forum={row[1] if row else None!r}")
    body_rows = db_query(after,
        "SELECT body FROM discussions WHERE author_username=? AND lower(title)=? AND forum=?",
        (USERNAME, TITLE, "Questions & Answers")) if after else None
    j.check("db_body_present", bool(body_rows and norm(body_rows[0][0])),
            f"body={body_rows[0][0] if body_rows else None!r}")
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/discussions/how-do-you-handle-class-imbalance")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a new discussion titled 'How do you handle class imbalance?' in Questions & Answers",
            "the created discussion thread")
        j.check("screenshot_shows_thread", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
