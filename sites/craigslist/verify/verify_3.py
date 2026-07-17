#!/usr/bin/env python3
"""Craigslist--3: log in as alice, find the 2006 Honda Accord EX sedan under $7000 with clean title
(id 13), open it, and save it.

TASK BUG (see review): id 13 is ALREADY in alice's pre-seeded saved listings (it is the item task
T13 later removes), so a genuine save is a no-op here and cannot be distinguished from the initial
state. This verifier checks navigation + that it is saved after; it CANNOT confirm the add. Fix the
task (use a non-pre-saved Accord, or drop the pre-seed) to make it verifiable.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, opened_listing, navigated_any, resolve_db, saved_listing_ids,
                        Judge, parse_args)
EMAIL = "alice.j@test.com"; LID = 13
def main():
    a = parse_args(); j = Judge('Craigslist--3', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_listing_or_save", opened_listing(t, LID) or navigated_any(t, ["/saved", f"/listing/{LID}/save"]),
            "expected the 2006 Honda Accord EX (id 13) / a save action")
    sa = saved_listing_ids(after, EMAIL) or []
    j.check("db_saved_present", LID in sa,
            f"Accord id {LID} must be in alice's saved listings (NOTE: pre-seeded; cannot confirm the add)")
    j.emit()
if __name__ == "__main__":
    main()
