#!/usr/bin/env python3
"""NVIDIA--13: sign in as alice, save the GeForce RTX 5070 Ti to the wishlist.
Deterministic-first: nav to the 5070 Ti page / wishlist | DB after-state: the 5070 Ti is in
alice's wishlist after AND was NOT there in the initial seed (proves the agent added it).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, wishlist_for, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "geforce-rtx-5070-ti"

def main():
    a = parse_args(); j = Judge('NVIDIA--13', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    wa = [s for s, _, _ in (wishlist_for(after, EMAIL) or [])]
    wi = [s for s, _, _ in (wishlist_for(init, EMAIL) or [])]
    j.check("nav_product_or_wishlist",
            navigated_any(t, [f"/products/{SLUG}", "/wishlist", "/account/wishlist"]),
            "expected the 5070 Ti page or the wishlist")
    j.check("db_wishlist_added", SLUG in wa and SLUG not in wi,
            f"5070 Ti in wishlist after={SLUG in wa}, initial={SLUG in wi}")
    j.emit()

if __name__ == "__main__":
    main()
