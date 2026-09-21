#!/usr/bin/env python3
"""Healthline--10: register a new account (myhealth2026 / myhealth2026@example.com) and land on
the account page. Deterministic-first: nav /register + /account | DB after-state: the new user
exists after AND not in the initial seed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (only_affirmative, affirmed_any, final_answer, resolve_base, password_verifies, user_row, load_run, navigated_to, navigated_any, resolve_db, user_exists, Judge, parse_args, run)

EMAIL = "myhealth2026@example.com"
USERNAME = "myhealth2026"
PASSWORD = "Wellness99!"

def main():
    a = parse_args(); j = Judge('Healthline--10', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    j.check("nav_register", navigated_to(t, "/register"), "expected the register page")
    j.check("nav_account", navigated_any(t, ["/account"]), "expected to land on the account page")
    j.check("db_user_created", user_exists(after, EMAIL) and not user_exists(init, EMAIL),
            f"user {EMAIL} after={user_exists(after, EMAIL)} initial={user_exists(init, EMAIL)}")
    row = user_row(after, EMAIL) if user_exists(after, EMAIL) else None
    j.check("db_username_matches", bool(row) and row[2] == USERNAME,
            f"expected username {USERNAME!r}; stored={row[2] if row else None!r}")
    ok_pw, pw_detail = password_verifies(row[3] if row else None, PASSWORD,
                                         base_url=resolve_base(a, t), email=EMAIL,
                                         container=a.container, live=not bool(a.after_db))
    if ok_pw is None:
        j.evidence.append(f"[SKIP] db_password_matches: {pw_detail}")
    else:
        j.check("db_password_matches", bool(ok_pw),
                f"the stored credential must accept {PASSWORD!r}: {pw_detail}")
    fa = final_answer(t)
    j.check("answer_affirms_registration",
            affirmed_any(fa, ["created", "registered"]) and only_affirmative(fa, ["created", "registered"]),
            f"expected the answer to report the successful registration; final={fa!r}")
    j.check_screenshots(t)
    j.emit()

if __name__ == '__main__':
    run(main, 'Healthline--10')
