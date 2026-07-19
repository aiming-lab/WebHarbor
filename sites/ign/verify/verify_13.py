#!/usr/bin/env python3
"""Deterministic verifier for IGN--13.

Log in as bob.c@test.com, go to Alerts, and pause the existing weekly-update guide alert.
Ground truth (after-state): bob's alert_subscriptions row with section_slug='guides' and
keyword containing 'weekly update' has active == 0 (paused). The seed creates it active=1,
so a no-op leaves it active -> FAIL.

Checks: nav login + alerts | DB after: guide/weekly-update alert inactive.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, last_shot, resolve_db, alert_rows,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "bob.c@test.com"

def main():
    a = parse_args()
    j = Judge('IGN--13', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_alerts", navigated_to(t, "/alerts"), f"alerts={navigated_to(t, '/alerts')}")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    rows = alert_rows(after, EMAIL)  # [(section, keyword, freq, active)]
    matched = paused = None
    if rows is not None:
        for section, keyword, freq, active in rows:
            if (section or "").lower() == "guides" and "weekly update" in (keyword or "").lower():
                matched = (section, keyword, freq, active)
                paused = not active
                break
    j.check("db_weekly_update_alert_paused", matched is not None and paused,
            f"match={matched!r} all={rows}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the weekly-update guide alert shown as paused/inactive",
            "bob's alerts list")
        j.check("screenshot_shows_paused", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
