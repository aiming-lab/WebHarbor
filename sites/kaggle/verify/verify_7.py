#!/usr/bin/env python3
"""Verifier for Kaggle--7 (stateful).

Sign in as alice.j@test.com and upvote the dataset 'World Happiness Report 2026'
(slug world-happiness-report-2026). Ground truth (after-state): a votes row (alice, 'dataset',
<dataset id>). Alice has no seed vote on it -> no-op FAILs.

Checks: nav login + dataset | DB after: vote row exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (Judge, id_by_slug, last_shot, llm_screenshot_shows, load_run,
                        navigated_to, origin_ok, parse_args, resolve_db, run_complete,
                        shot_at, shot_distinct, shot_final, vote_exists)

EMAIL = "alice.j@test.com"
SLUG = "world-happiness-report-2026"

def main():
    a = parse_args()
    j = Judge('Kaggle--7', a.no_llm)
    t = load_run(a.run_dir)
    after = resolve_db(a.after_db, a.container, "instance")
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    # Evidence binding: the graded mirror is a local origin, not the live upstream.
    origin_note_ok, origin_note = origin_ok(t)
    complete_ok, complete_note = run_complete(t)
    j.check("run_complete", complete_ok, complete_note)
    j.check("nav_origin_local", origin_note_ok, origin_note)
    j.check("nav_login", navigated_to(t, "/login"), f"login={navigated_to(t, '/login')}")
    j.check("nav_dataset", navigated_to(t, f"/datasets/{SLUG}"), "opened the World Happiness dataset")
    j.check("db_available", after is not None, f"after_db={'ok' if after else None}")
    did = id_by_slug(after, "datasets", SLUG) if after else None
    before_did = id_by_slug(init, "datasets", SLUG) if init else None
    before_voted = vote_exists(init, EMAIL, "dataset", before_did) if before_did else None
    voted = vote_exists(after, EMAIL, "dataset", did) if did else None
    j.check("db_upvoted", before_voted is False and voted is True,
            f"dataset_id={did} seed={before_voted} after={voted}")
    # Deterministic evidence binding: the target page must have a real,
    # decodable screenshot (a fabricated 1x1 image, or a page the run never
    # rendered, cannot satisfy this).
    shot_ok, shot_note = shot_at(t, "/datasets/world-happiness-report-2026")
    j.check("shot_target_page", shot_ok, shot_note)
    final_ok, final_note = shot_final(t)
    j.check("shot_final_page", final_ok, final_note)
    distinct_ok, distinct_note = shot_distinct(t)
    j.check("shot_frames_distinct", distinct_ok, distinct_note)
    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "the World Happiness Report 2026 dataset upvoted by the signed-in user",
            "the dataset page vote button state")
        j.check("screenshot_shows_vote", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
