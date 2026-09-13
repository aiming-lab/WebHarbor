#!/usr/bin/env python3
"""Verifier for Kaggle--12 (stateful).

Sign in as david.k@test.com and update the profile location to 'Boston, United States'.
Ground truth (after-state): david's users.location == 'Boston, United States'. Seed location
is 'Toronto, Canada' -> no-op FAILs.

Checks: nav login + account edit | DB after: location updated.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, user_location, norm,
                        last_shot, llm_screenshot_shows, Judge, parse_args)

EMAIL = "david.k@test.com"

def main():
    a = parse_args()
    j = Judge('Kaggle--12', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_account_edit", navigated_to(t, "/account/edit"), "opened the profile edit form")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    loc = user_location(after, EMAIL) if after else None
    before_loc = user_location(init, EMAIL) if init else None
    j.check("db_location_updated", norm(before_loc) != "boston, united states" and
            norm(loc) == "boston, united states",
            f"seed={before_loc!r} after={loc!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "profile location set to Boston, United States",
            "david's account/profile page")
        j.check("screenshot_shows_location", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
