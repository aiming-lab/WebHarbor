#!/usr/bin/env python3
"""NVIDIA--14: sign in as alice, change the country on the profile to Germany.
Deterministic-first: nav to /account/edit | DB after-state: alice's country is 'Germany'
after AND was something else initially (proves the agent changed it).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_any, resolve_db, user_field, Judge, parse_args)

EMAIL = "alice.j@test.com"

def main():
    a = parse_args(); j = Judge('NVIDIA--14', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ca = user_field(after, EMAIL, "country")
    ci = user_field(init, EMAIL, "country")
    j.check("nav_account_edit", navigated_any(t, ["/account/edit", "/account"]),
            "expected the profile edit page")
    j.check("db_country_germany",
            (ca or "").strip().lower() == "germany" and (ci or "").strip().lower() != "germany",
            f"country after={ca!r} initial={ci!r} (must become Germany)")
    j.emit()

if __name__ == "__main__":
    main()
