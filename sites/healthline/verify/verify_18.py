#!/usr/bin/env python3
"""Healthline--18: sign in as carol, change the account password from TestPass123! to NewPass456!.
Deterministic-first: nav /account/password | DB after-state: carol's password_hash changed from
its initial value (proves the password was actually updated).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, user_field, Judge, parse_args)

EMAIL = "carol.d@test.com"

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
    j.emit()

if __name__ == "__main__":
    main()
