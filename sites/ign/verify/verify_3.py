#!/usr/bin/env python3
"""Deterministic verifier for IGN--3.

Log in as david.k@test.com, create a daily Games alert for the keyword "PlayStation".
Ground truth (after-state): david has an alert_subscriptions row with section_slug='games',
keyword containing 'playstation', frequency='daily', active. The seed's games alert keyword
is his favorite platform ("Xbox Series X/S"), so a no-op has NO games+PlayStation alert -> FAIL.

Checks: nav login + alerts | DB after: matching alert row exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, last_shot, resolve_db, alert_rows,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "david.k@test.com"

def main():
    a = parse_args()
    j = Judge('IGN--3', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_alerts", navigated_to(t, "/alerts"), f"alerts={navigated_to(t, '/alerts')}")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    rows = alert_rows(after, EMAIL)  # [(section, keyword, freq, active)]
    hit = None
    if rows:
        for section, keyword, freq, active in rows:
            if (section or "").lower() == "games" and "playstation" in (keyword or "").lower() \
               and (freq or "").lower() == "daily" and active:
                hit = (section, keyword, freq, active)
                break
    j.check("db_games_playstation_daily_alert", after is not None and hit is not None,
            f"match={hit!r} all={rows}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a daily Games alert for the keyword PlayStation",
            "david's alerts list")
        j.check("screenshot_shows_alert", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
