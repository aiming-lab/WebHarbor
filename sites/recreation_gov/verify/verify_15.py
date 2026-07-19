#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--15.

Create a new account (display name River Stone, username river_stone, email
river.stone@example.com, password TrailPass2026). Report the default card ending and
default address city shown on the account page. Ground truth: register() seeds every
new account with a Visa ending 4242 and a Denver, CO default address.

Checks (deterministic first; DB after-state is authoritative):
nav /register | nav /account | DB: new user exists (not a seed email) | answer reports
card ending 4242 and city Denver
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, final_answer, contains_all,
                        resolve_db, user_row, SEED_EMAILS, Judge, parse_args)

EMAIL = "river.stone@example.com"

def main():
    a = parse_args()
    j = Judge('RecreationGov--15', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    after = resolve_db(a.after_db, a.container, "instance")
    row = user_row(after, EMAIL)  # (username, display_name, phone, home_city)
    j.check("nav_register", navigated_to(t, "/register") or navigated_to(t, "/create-account")
            or navigated_to(t, "/signup"), "reached account creation")
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    j.check("db_new_user", row is not None and EMAIL not in SEED_EMAILS,
            f"new user row={row}")
    j.check("answer_defaults", contains_all(fa, ["4242", "Denver"]), f"answer={fa!r}")
    j.emit()

if __name__ == "__main__":
    main()
