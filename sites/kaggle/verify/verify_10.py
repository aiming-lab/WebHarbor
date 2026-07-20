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
from verify_lib import (load_run, navigated_to, resolve_db, discussion_row, norm,
                        last_shot, llm_screenshot_shows, Judge, parse_args)

USERNAME = "alicejdata"
TITLE_SUBSTR = "how do you handle class imbalance"

def main():
    a = parse_args()
    j = Judge('Kaggle--10', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_new_discussion", navigated_to(t, "/discussions/new"), "opened the new-discussion form")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    row = discussion_row(after, USERNAME, TITLE_SUBSTR) if after else None  # (title, forum)
    j.check("db_discussion_created", row is not None, f"row={row!r}")
    j.check("db_forum_qa", row is not None and "questions & answers" in norm(row[1]),
            f"forum={row[1] if row else None!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a new discussion titled 'How do you handle class imbalance?' in Questions & Answers",
            "the created discussion thread")
        j.check("screenshot_shows_thread", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
