#!/usr/bin/env python3
"""Deterministic verifier for IGN--16.

Log in as alice.j@test.com, find the "Dragon Ball Xenoverse 2 - Official Future Saga Chapter 4
Trailer" video, and add it to Playlist as "queued".
Ground truth (after-state): alice has a playlist_entries row for that video (slug
dragon-ball-xenoverse-2-official-future-saga-chapter-4-trailer) with status == "queued". This
video is NOT in alice's seed playlist, so a no-op agent leaves no such row -> FAIL.

Checks: nav login + video | DB after: playlist row status=queued | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, playlist_row_for_item, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "dragon-ball-xenoverse-2-official-future-saga-chapter-4-trailer"

def main():
    a = parse_args()
    j = Judge('IGN--16', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_video", navigated_any(t, [SLUG]), "opened the Dragon Ball Xenoverse 2 trailer video")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    row = playlist_row_for_item(after, EMAIL, iid) if iid else None  # (status, note)
    j.check("db_playlist_queued", row is not None and norm(row[0]) == "queued",
            f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the Dragon Ball Xenoverse 2 trailer in the playlist with status queued",
            "alice's playlist")
        j.check("screenshot_shows_playlist", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
