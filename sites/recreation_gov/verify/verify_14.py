#!/usr/bin/env python3
"""Deterministic verifier for RecreationGov--14.

Log in as carol.d@test.com, update the account phone number to 555-0199 and the home
city to Boulder, then confirm both on the account page. Stateful — the User row is
authoritative (seed values were phone 555-0102, home_city Denver).

Checks (deterministic first; DB after-state is authoritative):
nav /account | DB: carol.phone == 555-0199 and carol.home_city == Boulder
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, user_row, norm,
                        Judge, parse_args)

EMAIL = "carol.d@test.com"

def main():
    a = parse_args()
    j = Judge('RecreationGov--14', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    row = user_row(after, EMAIL)  # (username, display_name, phone, home_city)
    phone = row[2] if row else None
    city = row[3] if row else None
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    j.check("db_phone_updated", phone == "555-0199", f"carol.phone={phone!r}")
    j.check("db_city_updated", norm(city) == norm("Boulder"), f"carol.home_city={city!r}")
    j.emit()

if __name__ == "__main__":
    main()
