#!/usr/bin/env python3
"""Deterministic verifier for IGN--0.

Log in as alice.j@test.com, search for "The Complicated History of GTA Controversies",
open the story, and save it to the Games folder with the note "gta controversy timeline".
Ground truth (after-state): alice has a saved_items row for the GTA-controversies story
(article or same-title video) with folder == "Games" and the note text present. The seed
already saves the article to "Read Later", so a no-op leaves folder != Games -> FAIL.

Checks: nav login + story detail | DB after: saved row folder=Games + note | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        resolve_db, item_ids_by_title_like, saved_row_for_item,
                        norm, llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
NOTE = "gta controversy timeline"

def main():
    a = parse_args()
    j = Judge('IGN--0', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_story", navigated_any(t, ["grand-theft-auto-controversies",
                                           "complicated-history-of-gta"]),
            "opened the GTA-controversies story detail page")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    ids = item_ids_by_title_like(after, "Complicated History of GTA") or []
    hit = None
    for iid in ids:
        row = saved_row_for_item(after, EMAIL, iid)  # (folder, note)
        if row and norm(row[0]) == "games" and NOTE in norm(row[1]):
            hit = row
            break
    j.check("db_saved_games_folder_with_note", after is not None and hit is not None,
            f"match={hit!r} candidates={ids}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the GTA controversies story saved to a 'Games' folder",
            "alice's saved stories / the save confirmation")
        j.check("screenshot_shows_save", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
