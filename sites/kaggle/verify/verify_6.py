#!/usr/bin/env python3
"""Verifier for Kaggle--6 (stateful).

Sign in as alice.j@test.com and join the 'LLM Prompt Recovery' competition
(slug llm-prompt-recovery) with team name 'Data Wizards'.
Ground truth (after-state): a competition_entries row for alice on that competition with
team_name containing 'data wizards'. Alice does NOT pre-join it in the seed -> no-op FAILs.

Checks: nav login + competition | DB after: entry with team name.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, competition_entry, norm,
                        last_shot, llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "llm-prompt-recovery"

def main():
    a = parse_args()
    j = Judge('Kaggle--6', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_competition", navigated_to(t, f"/competitions/{SLUG}"), "opened the LLM Prompt Recovery page")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    team = competition_entry(after, EMAIL, SLUG)  # team_name or None
    j.check("db_joined_with_team", team is not None and "data wizards" in norm(team),
            f"team={team!r}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "joined the LLM Prompt Recovery competition as team 'Data Wizards'",
            "alice's competition membership")
        j.check("screenshot_shows_join", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
