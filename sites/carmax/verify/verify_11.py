#!/usr/bin/env python3
"""Verifier for CarMax--11: sign in as bob.k, schedule an at-home test drive for any
2022 Ford F-150 on 2026-05-22 at 2:00 PM with note 'Please call gate buzzer 4B',
then confirm it shows on the test drives page.

Deterministic-first: nav login + test-drive + test-drives page | DB after-state: bob.k has an
at_home test drive for a 2022 Ford F-150 on 2026-05-22 2:00 PM with the note, not in seed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_any, resolve_db,
                        test_drives_for, norm, Judge, parse_args)

EMAIL = "bob.k@test.com"

def main():
    a = parse_args()
    j = Judge('CarMax--11', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    aft = test_drives_for(after, EMAIL) or []
    ini = test_drives_for(init, EMAIL) or []
    # row: (year, make, model, location_type, scheduled_date, scheduled_time, notes, status)
    def is_target(r):
        return (r[0] == 2022 and r[1] == "Ford" and r[2] == "F-150" and r[3] == "at_home"
                and str(r[4]) == "2026-05-22" and "2:00" in (r[5] or "")
                and "gate buzzer 4b" in norm(r[6]))
    new_td = [r for r in aft if is_target(r) and r not in ini]
    j.check("nav_login", navigated_to(t, "/login"), "expected /login")
    j.check("nav_test_drive", navigated_to(t, "/test-drive"), "expected a /test-drive flow")
    j.check("nav_test_drives_page", navigated_to(t, "/account/test-drives"), "expected test-drives page")
    j.check("db_at_home_f150_testdrive_with_note", bool(new_td),
            f"after={aft} initial={ini}")
    fa = final_answer(t)
    j.check("answer_confirms_testdrive", contains_any(fa, ["F-150", "test drive", "test-drive", "scheduled"]),
            f"expected the answer to confirm the F-150 at-home test drive; final={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
