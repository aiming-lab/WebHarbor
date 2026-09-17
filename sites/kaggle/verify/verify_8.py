#!/usr/bin/env python3
"""Verifier for Kaggle--8 (stateful).

Sign in as bob.c@test.com and save (bookmark) the notebook 'Titanic — Top 3% Solution
Walkthrough' (slug titanic-top-3-percent). Ground truth (after-state): a bookmarks row
(bob, 'notebook', <notebook id>). Bob's seed bookmark is a dataset, not this notebook -> no-op FAILs.

Checks: nav login + notebook | DB after: bookmark row exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, bookmark_exists, id_by_slug, last_shot,
                        llm_screenshot_shows, load_run, navigated_to, origin_ok,
                        parse_args, resolve_db, run_complete, shot_at, shot_distinct,
                        shot_final)

EMAIL = "bob.c@test.com"
SLUG = "titanic-top-3-percent"

def main():
    a = parse_args()
    j = Judge('Kaggle--8', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_notebook", navigated_to(t, f"/code/{SLUG}"), "opened the Titanic Top 3% notebook")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    nid = id_by_slug(after, "notebooks", SLUG) if after else None
    before_nid = id_by_slug(init, "notebooks", SLUG) if init else None
    before_marked = bookmark_exists(init, EMAIL, "notebook", before_nid) if before_nid else None
    marked = bookmark_exists(after, EMAIL, "notebook", nid) if nid else None
    j.check("db_bookmarked", before_marked is False and marked is True,
            f"notebook_id={nid} seed={before_marked} after={marked}")
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/code/titanic-top-3-percent")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the Titanic Top 3% notebook saved/bookmarked by the signed-in user",
            "the notebook page save-button state")
        j.check("screenshot_shows_bookmark", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
