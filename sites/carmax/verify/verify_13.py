#!/usr/bin/env python3
"""Verifier for CarMax--13: sign in as alice (who has two saved cars), remove the saved
vehicle with the HIGHER mileage, then report the year/make/model/store of the remaining one.

Deterministic-first: nav login + saved | DB after-state: the higher-mileage saved car is
gone and the lower-mileage one remains | answer names the remaining car.

Note (review): the task text says the two saved cars are "from different makes", but in the
seed both are Honda (2020 Civic 69k mi, 2021 CR-V 57.8k mi). The remove-higher-mileage step
is still deterministic; this verifier checks the actual data, not the (incorrect) wording.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all, resolve_db,
                        saved_vehicles_for, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge('CarMax--13', a.no_llm)
    t = load_run(a.run_dir); fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ini = saved_vehicles_for(init, EMAIL) or []   # rows: (year, make, model, trim, mileage) sorted by mileage
    aft = saved_vehicles_for(after, EMAIL) or []
    higher = max(ini, key=lambda r: r[4]) if ini else None   # should be removed
    lower = min(ini, key=lambda r: r[4]) if ini else None     # should remain
    j.check("nav_login", navigated_to(t, "/login"), "expected /login")
    # Saved cars are shown on both /saved and the /account page, so either is a valid path.
    j.check("nav_saved_or_account", navigated_to(t, "/saved") or navigated_to(t, "/account"),
            f"expected /saved or /account; urls={[s.get('url') for s in t.get('steps', [])]}")
    j.check("db_one_saved_remains", len(aft) == max(0, len(ini) - 1),
            f"initial_saved={len(ini)} after_saved={len(aft)}")
    j.check("db_higher_mileage_removed", bool(higher) and higher not in aft,
            f"higher-mileage car {higher} should be removed; after={aft}")
    j.check("db_lower_mileage_remains", bool(lower) and lower in aft,
            f"lower-mileage car {lower} should remain; after={aft}")
    if lower:
        j.check("answer_names_remaining", contains_all(fa, [str(lower[0]), lower[1], lower[2]]),
                f"expected remaining {lower[0]} {lower[1]} {lower[2]}; final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
