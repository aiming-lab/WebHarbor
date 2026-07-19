#!/usr/bin/env python3
"""Deterministic verifier for IGN--2.

Log in as bob.c@test.com, find "Will Nintendo Ever Stop Making Physical Games? - NVC Clips",
and add it to Playlist with the note "physical games debate".
Ground truth (after-state): bob has a playlist_entries row for that video with the note text
present. A no-op agent leaves no such row / no note -> FAIL.

Checks: nav login + video | DB after: playlist row + note | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, playlist_row_for_item, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"
SLUG = "will-nintendo-ever-stop-making-physical-games-nvc-clips"
NOTE = "physical games debate"

def main():
    a = parse_args()
    j = Judge('IGN--2', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_video", navigated_any(t, [SLUG]), "opened the NVC Clips video detail page")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    row = playlist_row_for_item(after, EMAIL, iid) if iid else None  # (status, note)
    j.check("db_playlist_with_note", row is not None and NOTE in norm(row[1]),
            f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"the NVC Clips video in a playlist with note '{NOTE}'",
            "bob's playlist")
        j.check("screenshot_shows_playlist", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
