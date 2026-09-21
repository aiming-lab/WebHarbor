#!/usr/bin/env python3
"""Deterministic verifier for IGN--5.

Log in as carol.d@test.com, update the account profile so the region is "San Francisco, CA"
and the favorite platform is "Nintendo Switch 2".
Ground truth (after-state): carol's users row has region containing "San Francisco" and
favorite_platform == "Nintendo Switch 2". The seed is region "Brooklyn, NY" / platform
"Nintendo Switch", so a no-op -> FAIL (and "Nintendo Switch" != "Nintendo Switch 2").

Checks: nav login + account edit | DB after: region + favorite_platform updated | LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, last_shot, resolve_db, user_profile,
                        norm, llm_screenshot_shows, Judge, parse_args)

EMAIL = "carol.d@test.com"

def main():
    a = parse_args()
    j = Judge('IGN--5', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_account_edit", navigated_to(t, "/account/edit"),
            f"edit={navigated_to(t, '/account/edit')}")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    prof = user_profile(after, EMAIL) if after else None  # (display_name, region, favorite_platform)
    region_ok = prof is not None and "san francisco" in norm(prof[1])
    plat_ok = prof is not None and norm(prof[2]) == "nintendo switch 2"
    j.check("db_region_updated", region_ok, f"region={prof[1] if prof else None!r}")
    j.check("db_platform_updated", plat_ok, f"favorite_platform={prof[2] if prof else None!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "region San Francisco, CA and favorite platform Nintendo Switch 2",
            "carol's account profile")
        j.check("screenshot_shows_profile", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
