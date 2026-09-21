#!/usr/bin/env python3
"""Deterministic verifier for IGN--18.

Log in as david.k@test.com, open the Movies section, find the "Anne Hathaway Quit Knocked Up"
story, and save it to the Weekend folder with the note "casting anecdote".
Ground truth (after-state): david has a saved_items row for the Anne Hathaway story with
folder == "Weekend" and the note text present. A no-op agent leaves no such row -> FAIL.

Checks: nav login + story | DB after: saved row folder=Weekend + note | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, saved_row_for_item, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "david.k@test.com"
SLUG = ("anne-hathaway-quit-knocked-up-because-she-didnt-want-the-crowning-of-the-baby-"
        "to-be-visually-representative-seth-rogen-says")
NOTE = "casting anecdote"

def main():
    a = parse_args()
    j = Judge('IGN--18', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_story", navigated_any(t, ["anne-hathaway-quit-knocked-up"]),
            "opened the Anne Hathaway story")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    row = saved_row_for_item(after, EMAIL, iid) if iid else None  # (folder, note)
    j.check("db_saved_weekend_with_note",
            row is not None and norm(row[0]) == "weekend" and NOTE in norm(row[1]),
            f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"the Anne Hathaway story saved to a 'Weekend' folder with note '{NOTE}'",
            "david's saved stories")
        j.check("screenshot_shows_save", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
