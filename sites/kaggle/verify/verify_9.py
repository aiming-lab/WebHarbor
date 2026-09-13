#!/usr/bin/env python3
"""Verifier for Kaggle--9 (stateful).

Sign in as bob.c@test.com and follow the user 'psi_grandmaster'. Ground truth (after-state):
a follows row (bob -> 'psi_grandmaster'). Bob has no seed follow -> no-op FAILs.

Checks: nav login + user profile | DB after: follow row exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, follow_exists, last_shot, llm_screenshot_shows, load_run,
                        navigated_to, origin_ok, parse_args, resolve_db, run_complete,
                        shot_at, shot_distinct, shot_final)

EMAIL = "bob.c@test.com"
TARGET = "psi_grandmaster"

def main():
    a = parse_args()
    j = Judge('Kaggle--9', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_profile", navigated_to(t, f"/user/{TARGET}"), "opened psi_grandmaster's profile")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    before_fol = follow_exists(init, EMAIL, TARGET)
    fol = follow_exists(after, EMAIL, TARGET)
    j.check("db_following", before_fol is False and fol is True,
            f"seed={before_fol} after={fol}")
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/user/psi_grandmaster")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the signed-in user now following psi_grandmaster",
            "the profile follow-button state")
        j.check("screenshot_shows_follow", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
