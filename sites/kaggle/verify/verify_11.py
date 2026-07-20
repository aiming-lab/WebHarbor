#!/usr/bin/env python3
"""Verifier for Kaggle--11 (stateful).

Sign in as david.k@test.com, open the discussion 'Underrated Titanic features that actually
help' (slug titanic-feature-ideas), and post a comment thanking the author. Ground truth
(after-state): david's username (davidtran) has MORE comments on that discussion than in the
seed (the seed already has one davidtran comment there, so an existence check is not enough —
we require the count to increase). A no-op agent leaves the count unchanged -> FAIL.

Checks: nav login + discussion | DB after: davidtran comment count on the thread increased.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, comment_by_on,
                        last_shot, llm_screenshot_shows, Judge, parse_args)

USERNAME = "davidtran"
SLUG = "titanic-feature-ideas"

def main():
    a = parse_args()
    j = Judge('Kaggle--11', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_discussion", navigated_to(t, f"/discussions/{SLUG}"), "opened the Titanic features discussion")
    before = comment_by_on(init, USERNAME, SLUG)
    now = comment_by_on(after, USERNAME, SLUG)
    j.check("db_available", before is not None and now is not None,
            f"seed={None if before is None else len(before)} after={None if now is None else len(now)}")
    j.check("db_comment_added", before is not None and now is not None and len(now) > len(before),
            f"seed_count={None if before is None else len(before)} after_count={None if now is None else len(now)}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a new comment by David (davidtran) on the Titanic features discussion",
            "the discussion comments section")
        j.check("screenshot_shows_comment", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
