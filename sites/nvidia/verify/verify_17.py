#!/usr/bin/env python3
"""NVIDIA--17: sign in as alice; among all GeForce Gaming cards with >=16 GB of memory, add
the least-expensive one to the cart.
Ground truth: GeForce RTX 5060 Ti ($429, 16 GB) — the cheapest GeForce Gaming card meeting
the >=16 GB constraint (the $299 RTX 5060 / RTX 4060 are only 8 GB; the $549 RTX 5070 is
12 GB — near-miss distractors that must be excluded).
Deterministic-first: nav to catalog/cart | DB after-state: alice's cart contains the 5060 Ti.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, cart_for, Judge, parse_args)

EMAIL = "alice.j@test.com"
TARGET = "geforce-rtx-5060-ti"

def main():
    a = parse_args(); j = Judge('NVIDIA--17', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    slugs = [s for s, _, _ in (cart_for(after, EMAIL) or [])]
    j.check("nav_catalog_or_cart", navigated_any(t, ["/products", "/cart"]),
            "expected browsing the catalog / cart")
    j.check("db_cart_has_5060ti", TARGET in slugs,
            f"cart must contain the RTX 5060 Ti (cheapest GeForce >=16GB); cart={slugs}")
    # guard against the two 8 GB near-misses being added instead
    wrong = {"geforce-rtx-5060", "geforce-rtx-4060", "geforce-rtx-5070"} & set(slugs)
    j.check("db_no_wrong_card", not wrong or TARGET in slugs,
            f"a sub-16GB near-miss was added: {wrong}")
    j.emit()

if __name__ == "__main__":
    main()
