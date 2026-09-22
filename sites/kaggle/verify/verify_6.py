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
from verify_lib import (Judge, competition_entry, last_shot, llm_screenshot_shows,
                        load_run, navigated_to, norm, origin_ok, parse_args, resolve_db,
                        run_complete, shot_at, shot_distinct, shot_final)

EMAIL = "alice.j@test.com"
SLUG = "llm-prompt-recovery"

def main():
    a = parse_args()
    j = Judge('Kaggle--6', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_competition", navigated_to(t, f"/competitions/{SLUG}"), "opened the LLM Prompt Recovery page")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    before_team = competition_entry(init, EMAIL, SLUG)
    team = competition_entry(after, EMAIL, SLUG)
    j.check("db_joined_with_team", before_team is None and norm(team) == "data wizards",
            f"seed_team={before_team!r} after_team={team!r}")
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/competitions/llm-prompt-recovery")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "joined the LLM Prompt Recovery competition as team 'Data Wizards'",
            "alice's competition membership")
        j.check("screenshot_shows_join", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
