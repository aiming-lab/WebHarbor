#!/usr/bin/env python3
"""Deterministic verifier for IGN--11.

Open the TV section, find "Everything Coming to HBO Max in July", and add it to Playlist after
logging in as david.k@test.com.
Ground truth (after-state): david has a playlist_entries row for the HBO Max July article
(slug whats-new-on-hbo-max-july-2026). A no-op agent leaves no such row -> FAIL.

Checks: nav login + TV + story | DB after: playlist row exists | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, playlist_row_for_item,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "david.k@test.com"
SLUG = "whats-new-on-hbo-max-july-2026"

def main():
    a = parse_args()
    j = Judge('IGN--11', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_story", navigated_any(t, [SLUG]), "opened the HBO Max July story")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    row = playlist_row_for_item(after, EMAIL, iid) if iid else None
    j.check("db_playlist_added", row is not None, f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the HBO Max July story added to david's playlist",
            "david's playlist")
        j.check("screenshot_shows_playlist", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
