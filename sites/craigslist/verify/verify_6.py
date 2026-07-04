#!/usr/bin/env python3
"""Craigslist--6: create a new posting in the bikes category for a blue commuter bike in Oakland
priced at $325 (body mentioning a rear rack and recently replaced brake pads).
Deterministic-first: nav /post | DB after-state: a new listing owned by alice in the bikes category,
area east bay/oakland, price 325."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, listings_by_owner, Judge, parse_args)
EMAIL = "alice.j@test.com"
def main():
    a = parse_args(); j = Judge('Craigslist--6', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    la = listings_by_owner(after, EMAIL) or []
    li = listings_by_owner(init, EMAIL) or []
    j.check("nav_post", navigated_to(t, "/post"), "expected the posting form")
    j.check("db_listing_created", len(la) > len(li), f"a new posting must exist: after={len(la)} initial={len(li)}")
    match = any(cat == "bikes" and float(price or 0) == 325 and
                ("oakland" in (area or "").lower() or "east bay" in (area or "").lower())
                for _, _, cat, area, price in la)
    j.check("db_bike_oakland_325", match, "the new posting must be a bikes/Oakland/$325 listing")
    j.emit()
if __name__ == "__main__":
    main()
