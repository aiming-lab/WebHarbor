#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--12.

Log in as bob.c@test.com and complete checkout for the item already in the cart
(seeded: Lake Powhatan Glamping). Then open Reservations and report the new confirmation
code. Stateful — the new Reservation row and emptied cart are authoritative.

Checks (deterministic first; DB after-state is authoritative):
nav /checkout | nav /reservations | DB: new numeric-coded reservation for lake-powhatan,
cart no longer holds it | answer reports the new confirmation code
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, norm,
                        resolve_db, reservations_for, cart_slugs_for, Judge, parse_args)

EMAIL = "bob.c@test.com"
SLUG = "lake-powhatan-glamping"
# Checkout assigns numeric codes RG-2026-NNNNN; seed reservations use RG-2026-XX01 form.
CODE_RE = re.compile(r"^RG-2026-\d{5}$")

def main():
    a = parse_args()
    j = Judge('RecreationGov--12', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    res = reservations_for(after, EMAIL) or []
    cart = cart_slugs_for(after, EMAIL)
    new_codes = [code for slug, code, status in res if slug == SLUG and CODE_RE.match(code or "")]
    j.check("nav_checkout", navigated_to(t, "/checkout"), f"navigated={navigated_to(t, '/checkout')}")
    j.check("nav_reservations", navigated_to(t, "/reservations"),
            f"navigated={navigated_to(t, '/reservations')}")
    j.check("db_new_reservation", bool(new_codes),
            f"new checkout reservations for {SLUG}: {new_codes}; all={res}")
    j.check("db_cart_emptied", cart is not None and SLUG not in cart, f"bob cart={cart}")
    j.check("answer_has_code", any(norm(c) in norm(fa) for c in new_codes),
            f"answer={fa!r} expected one of {new_codes}")
    j.emit()

if __name__ == "__main__":
    main()
