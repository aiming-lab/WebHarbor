#!/usr/bin/env python3
"""Craigslist--12: log in as alice and update the account area to peninsula and the phone number to
(650) 555-0144. Deterministic-first: nav /account/edit | DB after-state: alice's area is 'peninsula'
and her phone contains 650 555 0144."""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, user_field, Judge, parse_args)
EMAIL = "alice.j@test.com"
def main():
    a = parse_args(); j = Judge('Craigslist--12', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    area = (user_field(after, EMAIL, "area") or "").strip().lower()
    phone_digits = re.sub(r"\D", "", user_field(after, EMAIL, "phone") or "")
    j.check("nav_account_edit", navigated_any(t, ["/account/edit", "/account"]), "expected the account edit page")
    j.check("db_area_peninsula", area == "peninsula", f"area must be 'peninsula'; got {area!r}")
    j.check("db_phone_updated", "6505550144" in phone_digits, f"phone must be (650) 555-0144; digits={phone_digits}")
    j.emit()
if __name__ == "__main__":
    main()
