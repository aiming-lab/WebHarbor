#!/usr/bin/env python3
"""Verifier for Kaggle--8 (stateful).

Sign in as bob.c@test.com and save (bookmark) the notebook 'Titanic — Top 3% Solution
Walkthrough' (slug titanic-top-3-percent). Ground truth (after-state): a bookmarks row
(bob, 'notebook', <notebook id>). Bob's seed bookmark is a dataset, not this notebook -> no-op FAILs.

Checks: nav login + notebook | DB after: bookmark row exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, id_by_slug, bookmark_exists,
                        last_shot, llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"
SLUG = "titanic-top-3-percent"

def main():
    a = parse_args()
    j = Judge('Kaggle--8', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_notebook", navigated_to(t, f"/code/{SLUG}"), "opened the Titanic Top 3% notebook")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    nid = id_by_slug(after, "notebooks", SLUG) if after else None
    marked = bookmark_exists(after, EMAIL, "notebook", nid) if nid else None
    j.check("db_bookmarked", marked is True, f"notebook_id={nid} bookmarked={marked}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the Titanic Top 3% notebook saved/bookmarked by the signed-in user",
            "the notebook page save-button state")
        j.check("screenshot_shows_bookmark", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
