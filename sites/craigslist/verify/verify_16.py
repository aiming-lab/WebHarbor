#!/usr/bin/env python3
"""Craigslist--16: hide the Honda Passport project SUV listing (id 18) from search results, then
search Honda again and confirm the Accord and Odyssey remain visible.
Deterministic-first: nav | DB after-state: id 18 is in alice's hidden_listings after (and was not
initially), while the Accord (id 13) and any Odyssey remain un-hidden."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, hidden_listing_ids, Judge, parse_args)
EMAIL = "alice.j@test.com"; HIDE = 18
def main():
    a = parse_args(); j = Judge('Craigslist--16', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ha = hidden_listing_ids(after, EMAIL) or []
    hi = hidden_listing_ids(init, EMAIL) or []
    j.check("nav_hide", navigated_any(t, [f"/listing/{HIDE}/hide", "/search"]), "expected the hide action / search")
    j.check("db_passport_hidden", HIDE in ha and HIDE not in hi,
            f"Honda Passport id {HIDE} hidden after={HIDE in ha} initial={HIDE in hi}")
    j.check("db_others_not_hidden", 13 not in ha,
            "the Accord (id 13) must remain visible (not hidden)")
    j.emit()
if __name__ == "__main__":
    main()
