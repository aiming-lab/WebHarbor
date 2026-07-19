#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--19.

Log in as alice.j@test.com, open Yellowstone National Park Fishing Permit, add it to the
cart, and confirm it appears in Your cart. Stateful — the CartItem row is authoritative
(this permit was NOT seeded in alice's cart; she starts with Pinnacles only).

Checks (deterministic first; DB after-state is authoritative):
nav Yellowstone fishing permit detail | nav /cart | DB: permit in alice's cart
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, cart_slugs_for,
                        Judge, parse_args)

SLUG = "yellowstone-national-park-fishing-permit"

def main():
    a = parse_args()
    j = Judge('RecreationGov--19', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    cart = cart_slugs_for(after, "alice.j@test.com")
    j.check("nav_permit", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("nav_cart", navigated_to(t, "/cart"), f"navigated={navigated_to(t, '/cart')}")
    j.check("db_permit_in_cart", cart is not None and SLUG in cart, f"alice cart={cart}")
    j.emit()

if __name__ == "__main__":
    main()
