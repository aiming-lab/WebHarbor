#!/usr/bin/env python3
"""Deterministic verifier for IGN--14.

Log in as alice.j@test.com, go to Saved Stories, find the saved item in the Deals folder, and
remove it.
Ground truth (after-state): alice has ZERO saved_items rows with folder == "Deals". The seed
gives her exactly one Deals-folder saved item, so a no-op leaves the count at 1 -> FAIL.

Checks: nav login + saved | DB after: Deals-folder saved count == 0 (and was 1 in seed).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, last_shot, resolve_db, saved_folder_count,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge('IGN--14', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_saved", navigated_to(t, "/saved"), f"saved={navigated_to(t, '/saved')}")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    before = saved_folder_count(init, EMAIL, "Deals")
    now = saved_folder_count(after, EMAIL, "Deals")
    # Sanity: the seed must have had a Deals item to remove (else the task is vacuous).
    j.check("db_had_deals_item", before is not None and before >= 1, f"seed_deals_count={before}")
    j.check("db_deals_folder_emptied", now == 0, f"after_deals_count={now}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "no saved story remaining in the Deals folder",
            "alice's saved stories after removal")
        j.check("screenshot_shows_removed", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
