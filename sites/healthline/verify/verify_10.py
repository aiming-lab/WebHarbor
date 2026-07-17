#!/usr/bin/env python3
"""Healthline--10: register a new account (myhealth2026 / myhealth2026@example.com) and land on
the account page. Deterministic-first: nav /register + /account | DB after-state: the new user
exists after AND not in the initial seed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, resolve_db, user_exists,
                        Judge, parse_args)

EMAIL = "myhealth2026@example.com"

def main():
    a = parse_args(); j = Judge('Healthline--10', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_register", navigated_to(t, "/register"), "expected the register page")
    j.check("nav_account", navigated_any(t, ["/account"]), "expected to land on the account page")
    j.check("db_user_created", user_exists(after, EMAIL) and not user_exists(init, EMAIL),
            f"user {EMAIL} after={user_exists(after, EMAIL)} initial={user_exists(init, EMAIL)}")
    j.emit()

if __name__ == "__main__":
    main()
