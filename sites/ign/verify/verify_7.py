#!/usr/bin/env python3
"""Deterministic verifier for IGN--7.

Log in as alice.j@test.com, open the "Silo Season 3 Review", and post the comment
"Watch this before the finale.".
Ground truth (after-state): a comments row (alice, item silo-season-3-review) exists whose
body contains the posted text. A no-op agent posts no comment -> FAIL.

Checks: nav login + review | DB after: comment body present | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, comment_bodies, norm,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "silo-season-3-review"
COMMENT = "watch this before the finale"

def main():
    a = parse_args()
    j = Judge('IGN--7', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_review", navigated_any(t, [SLUG]), "opened the Silo Season 3 review")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    bodies = comment_bodies(after, EMAIL, iid) if iid else None
    posted = bodies is not None and any(COMMENT in norm(b) for b in bodies)
    j.check("db_comment_posted", posted, f"item_id={iid} bodies={bodies!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"the reader comment '{COMMENT}' on the Silo Season 3 review",
            "the Silo review comments section")
        j.check("screenshot_shows_comment", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
