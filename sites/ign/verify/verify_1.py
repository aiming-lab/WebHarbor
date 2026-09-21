#!/usr/bin/env python3
"""Deterministic verifier for IGN--1.

Log in as alice.j@test.com, find the "GTA Online Weekly Updates" guide, and mark the
checklist item "Claim Independence Day freebies" as complete.
Ground truth (after-state): the guide_progress row (alice, guide gta-online-weekly-updates,
checkpoint "Claim Independence Day freebies") has completed = 1. The seed leaves this
checkpoint incomplete, so a no-op -> completed False/None -> FAIL.

Checks: nav login + guide | DB after: checkpoint completed=1 | LLM screenshot.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, last_shot, resolve_db,
                        item_id_by_slug, guide_checkpoint_completed,
                        llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "gta-online-weekly-updates"
CHECKPOINT = "Claim Independence Day freebies"

def main():
    a = parse_args()
    j = Judge('IGN--1', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_guide", navigated_any(t, ["GTA_Online_Weekly_Updates", SLUG]),
            "opened the GTA Online Weekly Updates guide")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    iid = item_id_by_slug(after, SLUG) if after else None
    done = guide_checkpoint_completed(after, EMAIL, iid, CHECKPOINT) if iid else None
    j.check("db_checkpoint_completed", done is True,
            f"item_id={iid} checkpoint={CHECKPOINT!r} completed={done}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"the checklist item '{CHECKPOINT}' marked complete",
            "the GTA Online Weekly Updates guide checklist")
        j.check("screenshot_shows_checked", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
