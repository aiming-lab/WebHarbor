#!/usr/bin/env python3
"""Verifier for Kaggle--12 (stateful).

Sign in as david.k@test.com and update the profile location to 'Boston, United States'.
Ground truth (after-state): david's users.location == 'Boston, United States'. Seed location
is 'Toronto, Canada' -> no-op FAILs.

Checks: nav login + account edit | DB after: location updated.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, last_shot, llm_screenshot_shows, load_run, navigated_to,
                        norm, origin_ok, parse_args, resolve_db, run_complete, shot_at,
                        shot_distinct, shot_final, user_location)

EMAIL = "david.k@test.com"

def main():
    a = parse_args()
    j = Judge('Kaggle--12', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_account_edit", navigated_to(t, "/account/edit"), "opened the profile edit form")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    loc = user_location(after, EMAIL) if after else None
    before_loc = user_location(init, EMAIL) if init else None
    j.check("db_location_updated", norm(before_loc) != "boston, united states" and
            norm(loc) == "boston, united states",
            f"seed={before_loc!r} after={loc!r}")
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/user/davidtran")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "profile location set to Boston, United States",
            "david's account/profile page")
        j.check("screenshot_shows_location", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
