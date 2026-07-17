#!/usr/bin/env python3
"""Craigslist--0: log in as alice, search furniture east bay for a chair under $100 with adjustable
arms, open it, and save it. Target = 'Ergonomic task chair' (id 1, $85, arms: adjustable).

TASK BUG (see review): id 1 is ALREADY in alice's pre-seeded saved listings, so a genuine save is a
no-op and can't be distinguished from the initial state. This verifier checks navigation to the
listing + that it is saved after; it CANNOT confirm the agent added it. Fix the task (use a
non-pre-saved chair) to make it verifiable.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, opened_listing, navigated_any, resolve_db, saved_listing_ids,
                        Judge, parse_args)
EMAIL = "alice.j@test.com"; LID = 1
def main():
    a = parse_args(); j = Judge('Craigslist--0', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_listing_or_saved", opened_listing(t, LID) or navigated_any(t, ["/saved", f"/listing/{LID}/save"]),
            "expected the adjustable-arms chair (id 1) / a save action")
    sa = saved_listing_ids(after, EMAIL) or []
    j.check("db_saved_present", LID in sa,
            f"chair id {LID} must be in alice's saved listings (NOTE: pre-seeded; cannot confirm the add)")
    j.emit()
if __name__ == "__main__":
    main()
