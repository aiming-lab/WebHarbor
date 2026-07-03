#!/usr/bin/env python3
"""NVIDIA--15: sign in as alice, write a 5-star review titled 'Incredible' for the Jetson
Orin Nano Super Developer Kit.
Deterministic-first: nav to the Jetson product page | DB after-state: a NEW review by alice
on that product exists with rating 5 and title containing 'Incredible'.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, reviews_for, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "jetson-orin-nano-super"

def main():
    a = parse_args(); j = Judge('NVIDIA--15', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ra = reviews_for(after, EMAIL, SLUG) or []
    ri = reviews_for(init, EMAIL, SLUG) or []
    j.check("nav_product", navigated_to(t, f"/products/{SLUG}"),
            "expected the Jetson Orin Nano Super page")
    j.check("db_review_created", len(ra) > len(ri),
            f"reviews by alice on the Jetson after={len(ra)} vs initial={len(ri)}")
    match = any(r[1] == 5 and "incredible" in (r[2] or "").lower() for r in ra)
    j.check("db_review_5star_titled", match,
            "a review with rating=5 and title 'Incredible' must exist")
    j.emit()

if __name__ == "__main__":
    main()
