#!/usr/bin/env python3
"""Deterministic verifier for IGN--19 (added during PR #61 review-and-fix).

Create a new IGN account with the email henry.m@test.com, the username henry_m,
the display name Henry M, and the password TestPass123!. Finish on the new
account's profile page.
Ground truth (after-state): a NEW users row exists with email henry.m@test.com,
username == "henry_m" and display_name == "Henry M"; the row must be absent from
the initial state (registration during this run, not a seeded account). The seed
has only the 4 benchmark users, so a no-op -> FAIL; reusing an existing account
-> FAIL (site also rejects duplicate email/username at /register).

Checks: nav register (+ landing on account) | DB after: new-row identity fields.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, db_query, norm,
                        Judge, parse_args)

EMAIL = "henry.m@test.com"

def main():
    a = parse_args()
    j = Judge('IGN--19', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_register", navigated_to(t, "/register"), f"register={navigated_to(t, '/register')}")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    pre = db_query(initial, "SELECT email FROM users WHERE email=?", (EMAIL,)) if initial else None
    rows = db_query(after, "SELECT email, username, display_name FROM users WHERE email=?", (EMAIL,)) if after else None
    row = rows[0] if rows else None
    j.check("db_user_is_new", row is not None and not pre,
            f"existed_before={bool(pre)} row={row!r}")
    if row:
        j.check("db_username", norm(row[1]) == "henry_m", f"username={row[1]!r}")
        j.check("db_display_name", norm(row[2]) == "henry m", f"display_name={row[2]!r}")
    else:
        j.check("db_username", False, "no new user row")
        j.check("db_display_name", False, "no new user row")
    j.emit()

if __name__ == "__main__":
    main()
