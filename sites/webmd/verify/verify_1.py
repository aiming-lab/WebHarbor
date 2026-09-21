#!/usr/bin/env python3
"""Deterministic verifier for WebMD--1.

Health News > Research & Approvals > RSV vaccine for adults in their 50s;
report published AND medically-reviewed dates.
Ground truth: published December 23, 2024; reviewed December 27, 2024.

Checks: nav article page | both dates present (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--1', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/articles/rsv-vaccine-adults-50s"),
            f"navigated={navigated_to(t, '/articles/rsv-vaccine-adults-50s')}")
    j.check("answer_has_published_date", date_present(fa, 2024, 12, 23), f"final={fa!r}")
    j.check("answer_has_reviewed_date", date_present(fa, 2024, 12, 27), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Published December 23, 2024; medically reviewed December 27, 2024",
        "What are the published date and medically-reviewed date of the RSV-vaccine-for-adults-50s article?")
    j.check("answer_dates_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/articles/rsv-vaccine-adults-50s") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Published December 23, 2024 · Reviewed December 27, 2024",
            "the published/reviewed date line of the RSV vaccine article")
        j.check("screenshot_shows_dates", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
