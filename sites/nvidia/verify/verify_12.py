#!/usr/bin/env python3
"""NVIDIA--12: sign in as alice, add the least-expensive GeForce RTX 40 Series card to cart.
Ground truth: GeForce RTX 4060 ($299, the cheapest RTX 40 Series).
Deterministic-first: nav to catalog/cart | DB after-state: alice's cart contains the 4060.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, cart_for, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args(); j = Judge('NVIDIA--12', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    cart = cart_for(after, EMAIL)
    j.check("nav_catalog_or_cart", navigated_any(t, ["/products", "/cart"]),
            "expected browsing the catalog / cart")
    slugs = [s for s, _, _ in (cart or [])]
    j.check("db_cart_has_4060", "geforce-rtx-4060" in slugs,
            f"alice's cart must contain the RTX 4060 (cheapest RTX 40); cart={slugs}")
    j.emit()

if __name__ == "__main__":
    main()
