#!/usr/bin/env python3
"""Verifier for CarMax--10: sign in as alice, reserve any 2022 Toyota Camry for 7 days
with appointment date 2026-05-20, then confirm it is listed as active.

Deterministic-first: nav login + reserve + reservations page | DB after-state: alice has an
ACTIVE reservation for a 2022 Toyota Camry appt 2026-05-20 that was NOT in the initial seed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any, resolve_db,
                        reservations_for, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args()
    j = Judge('CarMax--10', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    aft = reservations_for(after, EMAIL, "active") or []
    ini = reservations_for(init, EMAIL, "active") or []
    def is_target(r):  # (year, make, model, appointment_date, status)
        return r[0] == 2022 and r[1] == "Toyota" and r[2] == "Camry" and str(r[3]) == "2026-05-20"
    new_camry = [r for r in aft if is_target(r) and r not in ini]
    j.check("nav_login", navigated_to(t, "/login"), "expected /login")
    j.check("nav_reserve", navigated_to(t, "/reserve"), "expected a /reserve flow")
    j.check("nav_reservations", navigated_to(t, "/account/reservations"), "expected reservations page")
    j.check("db_active_2022_camry_reservation_2026_05_20", bool(new_camry),
            f"after_active={aft} initial_active={ini}")
    fa = final_answer(t)
    j.check("answer_confirms_reservation", contains_any(fa, ["Camry", "reserved", "reservation", "active"]),
            f"expected the answer to confirm the active 2022 Camry reservation; final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
