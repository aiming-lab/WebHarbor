#!/usr/bin/env python3
"""Healthline--18: sign in as carol, change the account password from TestPass123! to NewPass456!.
Deterministic-first: nav /account/password | DB after-state: carol's password_hash changed from
its initial value (proves the password was actually updated).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (only_affirmative, affirmed_any, final_answer, resolve_base, password_verifies, load_run, navigated_to, resolve_db, user_field, Judge, parse_args, run)

EMAIL = "carol.d@test.com"
NEW_PASSWORD = "NewPass456!"
OLD_PASSWORD = "TestPass123!"

def main():
    a = parse_args(); j = Judge('Healthline--18', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ha = user_field(after, EMAIL, "password_hash")
    hi = user_field(init, EMAIL, "password_hash")
    j.check("nav_password", navigated_to(t, "/account/password"), "expected the change-password page")
    j.check("db_password_changed", bool(ha) and bool(hi) and ha != hi,
            f"carol's password_hash must change (initial != after)")
    base = resolve_base(a, t)
    live = not bool(a.after_db)
    ok_new, new_detail = password_verifies(ha, NEW_PASSWORD, base_url=base, email=EMAIL,
                                           container=a.container, live=live)
    ok_old, old_detail = password_verifies(ha, OLD_PASSWORD, base_url=base, email=EMAIL,
                                           container=a.container, live=live)
    if ok_new is None:
        j.evidence.append(f"[SKIP] db_new_password_works: {new_detail}")
    else:
        j.check("db_new_password_works", bool(ok_new),
                f"the stored credential must accept the new password {NEW_PASSWORD!r}: {new_detail}")
    if ok_old is None:
        j.evidence.append(f"[SKIP] db_old_password_rejected: {old_detail}")
    else:
        j.check("db_old_password_rejected", not ok_old,
                f"the old password {OLD_PASSWORD!r} must stop working: {old_detail}")
    fa = final_answer(t)
    j.check("answer_affirms_change",
            affirmed_any(fa, ["changed", "updated", "Password updated"])
            and only_affirmative(fa, ["changed", "updated"]),
            f"expected the answer to report the successful password change; final={fa!r}")
    j.check_screenshots(t)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--18')
