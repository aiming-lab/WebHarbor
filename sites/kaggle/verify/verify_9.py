#!/usr/bin/env python3
"""Verifier for Kaggle--9 (stateful).

Sign in as bob.c@test.com and follow the user 'psi_grandmaster'. Ground truth (after-state):
a follows row (bob -> 'psi_grandmaster'). Bob has no seed follow -> no-op FAILs.

Checks: nav login + user profile | DB after: follow row exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, follow_exists,
                        last_shot, llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"
TARGET = "psi_grandmaster"

def main():
    a = parse_args()
    j = Judge('Kaggle--9', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_profile", navigated_to(t, f"/user/{TARGET}"), "opened psi_grandmaster's profile")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    fol = follow_exists(after, EMAIL, TARGET)
    j.check("db_following", fol is True, f"following={fol}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the signed-in user now following psi_grandmaster",
            "the profile follow-button state")
        j.check("screenshot_shows_follow", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
