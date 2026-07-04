#!/usr/bin/env python3
"""Craigslist--13: log in as alice, open saved listings, remove the saved Honda Accord (id 13),
leaving the saved furniture (chair id 1) and apartment (studio id 21) untouched.
Deterministic-first: nav /saved | DB after-state: id 13 was saved initially and is GONE after, while
id 1 and id 21 remain saved."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, saved_listing_ids, Judge, parse_args)
EMAIL = "alice.j@test.com"; REMOVE = 13; KEEP = [1, 21]
def main():
    a = parse_args(); j = Judge('Craigslist--13', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    sa = saved_listing_ids(after, EMAIL) or []
    si = saved_listing_ids(init, EMAIL) or []
    j.check("nav_saved", navigated_any(t, ["/saved", "/listing/13/unsave"]), "expected the saved listings page")
    j.check("db_accord_removed", REMOVE in si and REMOVE not in sa,
            f"Accord id {REMOVE} initial={REMOVE in si} after={REMOVE in sa} (must be removed)")
    j.check("db_others_kept", all(k in sa for k in KEEP),
            f"the chair (1) and studio (21) must remain saved; after={sa}")
    j.emit()
if __name__ == "__main__":
    main()
