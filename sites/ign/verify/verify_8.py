#!/usr/bin/env python3
"""Deterministic verifier for IGN--8.

Log in as david.k@test.com, go to the Videos section, find the video "PlayStation's Physical
Media-Free Future Isn't Just Concerning, It's Offensive", and add it to Playlist with status
"watching".
Ground truth (after-state): david has a playlist_entries row for the VIDEO (slug ...-offensive-video,
NOT the same-title article) with status == "watching". A no-op leaves no such row -> FAIL.

Note: there is a same-title article (id 2) and video (id 39). This task targets the video.

Checks: nav login + videos + video detail | DB after: playlist status=watching | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, playlist_row_for_item, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "david.k@test.com"
VIDEO_SLUG = "playstations-physical-media-free-future-isnt-just-concerning-its-offensive-video"

def main():
    a = parse_args()
    j = Judge('IGN--8', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_video", navigated_to(t, VIDEO_SLUG), "opened the PlayStation physical-media VIDEO")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, VIDEO_SLUG) if after else None
    row = playlist_row_for_item(after, EMAIL, iid) if iid else None  # (status, note)
    j.check("db_playlist_watching", row is not None and norm(row[0]) == "watching",
            f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the PlayStation physical-media video in the playlist with status watching",
            "david's playlist")
        j.check("screenshot_shows_playlist", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
