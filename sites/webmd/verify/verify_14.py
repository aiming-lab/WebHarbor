#!/usr/bin/env python3
"""Deterministic verifier for WebMD--14.

Find the medical reviewer board-certified in Gastroenterology; report her name and
how many articles she has medically reviewed on this site.
Ground truth: Lucia Ferreira, MD; 5 articles reviewed.

The count is verified deterministically against the DB (reviewer_id join), so it is
robust to catalog changes. Nav to the author profile is the anti-shortcut gate.

Checks: nav author profile | answer names Ferreira + count (deterministic, DB-cross-checked) | LLM+screenshot anchored.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        shot_after_url, contains_all, contains_any, contains_number,
                        answer_equals, date_present, resolve_db, saved_slugs_for,
                        saved_count_for, user_exists, password_hash_for, password_matches,
                        db_query, llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('WebMD--14', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_author_profile", navigated_to(t, "/authors/lucia-ferreira-md"),
            f"navigated={navigated_to(t, '/authors/lucia-ferreira-md')}")
    # DB cross-check the reviewed count. Fail closed if the seed DB is unavailable
    # (do NOT fall back to a hard-coded constant — that would grade against a guess).
    init = resolve_db(a.initial_db, a.container, "instance_seed")
    reviewed = None
    if init:
        rows = db_query(init,
            "SELECT count(*) FROM articles ar JOIN authors au ON au.id=ar.reviewer_id "
            "WHERE au.slug='lucia-ferreira-md'")
        reviewed = rows[0][0] if rows else None
    j.check("db_available", reviewed is not None, f"reviewed_count={reviewed}")
    j.check("answer_names_reviewer", contains_any(fa, ["ferreira"]), f"final={fa!r}")
    j.check("answer_review_count", reviewed is not None and contains_number(fa, reviewed),
            f"expected={reviewed} final={fa!r}")
    ok, ev = llm_text_match(fa, f"Lucia Ferreira, MD; she has medically reviewed {reviewed} articles on this site",
        "Which reviewer is board-certified in Gastroenterology and how many articles has she reviewed here?")
    j.check("answer_details_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/authors/lucia-ferreira-md") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, f"Lucia Ferreira — {reviewed} medically reviewed articles",
            "the Lucia Ferreira author profile listing reviewed articles")
        j.check("screenshot_shows_profile", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
