#!/usr/bin/env python3
"""Deterministic verifier for IGN--12.

Log in as alice.j@test.com, search "physical media future", open the PlayStation ARTICLE, and
save it to Read Later.
Ground truth (after-state): alice's saved_items row for the article (id 2,
slug ...-offensive, served at /articles/...) has folder == "Read Later". The seed already saves
this article under "Weekend", so a no-op leaves folder == Weekend -> FAIL.

Note: a same-title VIDEO (id 39) exists; this task targets the ARTICLE, so nav is checked on
the /articles/ path specifically.

Checks: nav login + /articles/<slug> | DB after: saved folder=Read Later | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, last_shot, resolve_db,
                        item_id_by_slug, saved_row_for_item, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
ARTICLE_SLUG = "playstations-physical-media-free-future-isnt-just-concerning-its-offensive"

def main():
    a = parse_args()
    j = Judge('IGN--12', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    # /articles/<slug> distinguishes the article from the same-title video (/videos/...-video).
    j.check("nav_article", navigated_to(t, f"/articles/{ARTICLE_SLUG}"),
            "opened the PlayStation physical-media ARTICLE (not the video)")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, ARTICLE_SLUG) if after else None
    row = saved_row_for_item(after, EMAIL, iid) if iid else None  # (folder, note)
    j.check("db_saved_read_later", row is not None and norm(row[0]) == "read later",
            f"item_id={iid} row={row!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the PlayStation article saved to the 'Read Later' folder",
            "alice's saved stories")
        j.check("screenshot_shows_save", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
