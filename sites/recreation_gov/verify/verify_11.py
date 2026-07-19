#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--11.

Log in as alice.j@test.com, save Fort Point National Historic Site Tours, and confirm
it appears in Saved locations. Stateful — strongest signal is the SavedItem row.

Checks (deterministic first; DB after-state is authoritative):
nav Fort Point detail | nav /saved | DB: fort-point saved by alice (was NOT seeded)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, saved_slugs_for,
                        Judge, parse_args)

SLUG = "fort-point-national-historic-site-tours"

def main():
    a = parse_args()
    j = Judge('RecreationGov--11', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    saved = saved_slugs_for(after, "alice.j@test.com")
    j.check("nav_fort_point", navigated_to(t, SLUG), f"navigated={navigated_to(t, SLUG)}")
    j.check("nav_saved", navigated_to(t, "/saved"), f"navigated={navigated_to(t, '/saved')}")
    j.check("db_fort_point_saved", saved is not None and SLUG in saved,
            f"alice saved={saved}")
    j.emit()

if __name__ == "__main__":
    main()
