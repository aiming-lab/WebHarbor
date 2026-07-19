#!/usr/bin/env python3
"""Deterministic verifier for WebMD--17.

Log in as bob.m@test.com, change the password to NewPass456! in account settings,
log out, and log back in with the new password.
Ground truth (after-state): bob's stored password hash DIFFERS from the seed hash
(a change occurred). If bcrypt is available, it must verify NewPass456! exactly;
otherwise that exact-match check is skipped and the hash-changed signal stands.

Checks: nav /account + re-login | DB after: bob hash changed (+ optional bcrypt match) | LLM+screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        shot_after_url, contains_all, contains_any, answer_equals,
                        date_present, resolve_db, saved_slugs_for, saved_count_for,
                        user_exists, password_hash_for, password_matches,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.m@test.com"
NEW_PW = "NewPass456!"

def main():
    a = parse_args()
    j = Judge('WebMD--17', a.no_llm)
    t = load_run(a.run_dir)
    j.check("nav_account", navigated_to(t, "/account"), f"navigated={navigated_to(t, '/account')}")
    # The task requires log out THEN log back in. Require an explicit /logout visit
    # plus >=2 /login visits — a single login flow can hit /login twice (the
    # login-required redirect + the form submit), so the logout visit is the real signal.
    j.check("logged_out", navigated_to(t, "/logout"),
            f"navigated_logout={navigated_to(t, '/logout')}")
    j.check("re_logged_in", navigated_to(t, "/login", times=2),
            f"login_visits={sum(1 for u in [s.get('url','') for s in t.get('steps', [])] if '/login' in u)}")
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    ah = password_hash_for(after, EMAIL)
    ih = password_hash_for(init, EMAIL)
    j.check("db_password_changed", ah is not None and ih is not None and ah != ih,
            f"changed={ah != ih if (ah and ih) else None}")
    # Optional exact-password confirmation (skipped when bcrypt unavailable).
    match = password_matches(after, EMAIL, NEW_PW)
    j.check("db_new_password_verifies", match, f"bcrypt_match={match}", llm=(match is None))
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "logged in as Bob Martinez (account page / My WebMD)",
            "the page confirming a successful re-login after the password change")
        j.check("screenshot_shows_relogin", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
