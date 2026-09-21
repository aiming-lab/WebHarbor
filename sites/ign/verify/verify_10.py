#!/usr/bin/env python3
"""Deterministic verifier for IGN--10.

Log in as carol.d@test.com, open the "Fortnite Guide", and save it with the note "weekly quests".
Ground truth (after-state): carol has a saved_items row for the Fortnite guide (slug 'fortnite')
whose note contains "weekly quests". A no-op agent leaves no such saved row -> FAIL.

Checks: nav login + guide | DB after: saved row + note | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, saved_row_for_item, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "carol.d@test.com"
SLUG = "fortnite"
NOTE = "weekly quests"

def main():
    a = parse_args()
    j = Judge('IGN--10', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_guide", navigated_any(t, ["/wikis/fortnite", "wikis/fortnite"]),
            "opened the Fortnite guide")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    row = saved_row_for_item(after, EMAIL, iid) if iid else None  # (folder, note)
    j.check("db_saved_with_note", row is not None and NOTE in norm(row[1]),
            f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"the Fortnite guide saved with note '{NOTE}'",
            "carol's saved stories")
        j.check("screenshot_shows_save", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
