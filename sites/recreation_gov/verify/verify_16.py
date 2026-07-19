#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--16.

Log in as david.k@test.com, open Fort Point National Historic Site Tours, and submit a
4-star review with visit date May 2026 and the note 'Accessible route was easy to
follow.', then confirm it appears with the Your review badge. Stateful — the new Review
row (author David Kim) is authoritative; no such review is seeded.

Checks (deterministic first; DB after-state is authoritative):
nav Fort Point detail | DB: David Kim review on Fort Point with rating 4 and the note text
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, reviews_for, norm,
                        Judge, parse_args)

SLUG = "fort-point-national-historic-site-tours"
NOTE = "accessible route was easy to follow"

def main():
    a = parse_args()
    j = Judge('RecreationGov--16', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    rows = reviews_for(after, SLUG, author="David Kim")  # (author, rating, body, visit_date)
    match = [r for r in (rows or [])
             if r[1] == 4 and NOTE in norm(r[2]) and "may 2026" in norm(r[3])]
    j.check("nav_fort_point", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("db_review_submitted", bool(match),
            f"David Kim reviews on Fort Point={rows}")
    j.emit()

if __name__ == "__main__":
    main()
