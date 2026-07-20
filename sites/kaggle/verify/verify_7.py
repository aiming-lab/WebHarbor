#!/usr/bin/env python3
"""Verifier for Kaggle--7 (stateful).

Sign in as alice.j@test.com and upvote the dataset 'World Happiness Report 2026'
(slug world-happiness-report-2026). Ground truth (after-state): a votes row (alice, 'dataset',
<dataset id>). Alice has no seed vote on it -> no-op FAILs.

Checks: nav login + dataset | DB after: vote row exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, resolve_db, id_by_slug, vote_exists,
                        last_shot, llm_screenshot_shows, Judge, parse_args)

EMAIL = "alice.j@test.com"
SLUG = "world-happiness-report-2026"

def main():
    a = parse_args()
    j = Judge('Kaggle--7', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_dataset", navigated_to(t, f"/datasets/{SLUG}"), "opened the World Happiness dataset")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    did = id_by_slug(after, "datasets", SLUG) if after else None
    voted = vote_exists(after, EMAIL, "dataset", did) if did else None
    j.check("db_upvoted", voted is True, f"dataset_id={did} voted={voted}")
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the World Happiness Report 2026 dataset upvoted by the signed-in user",
            "the dataset page vote button state")
        j.check("screenshot_shows_vote", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
