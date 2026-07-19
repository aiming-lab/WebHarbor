#!/usr/bin/env python3
"""Deterministic verifier for WebMD--5.

Search "melatonin" > "What the Evidence Supports" article; report its medical
reviewer, then open that reviewer's author profile and report the credentials.
Ground truth: reviewer = Steven Marsh, PharmD; credentials = PharmD, BCPS.

Checks: nav article + reviewer profile | answer names reviewer + credentials (deterministic) | LLM+screenshot anchored.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        shot_after_url, contains_all, contains_any, answer_equals,
                        date_present, resolve_db, saved_slugs_for, saved_count_for,
                        user_exists, password_hash_for, password_matches,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('WebMD--5', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/articles/melatonin-evidence"),
            f"navigated={navigated_to(t, '/articles/melatonin-evidence')}")
    j.check("nav_reviewer_profile", navigated_to(t, "/authors/steven-marsh-pharmd"),
            f"navigated={navigated_to(t, '/authors/steven-marsh-pharmd')}")
    j.check("answer_reviewer_and_creds",
            contains_all(fa, ["marsh"]) and contains_any(fa, ["pharmd"]) and contains_any(fa, ["bcps"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Reviewer Steven Marsh, PharmD; credentials PharmD, BCPS",
        "Who medically reviewed the melatonin evidence article and what credentials are on that reviewer's profile?")
    j.check("answer_creds_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/authors/steven-marsh-pharmd") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Steven Marsh — PharmD, BCPS",
            "the reviewer's author-profile credentials")
        j.check("screenshot_shows_creds", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
