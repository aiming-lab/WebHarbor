#!/usr/bin/env python3
"""Deterministic verifier for WebMD--7.

Levothyroxine drug page; report the category label at the top and the conditions
listed in its 'Used For' sidebar.
Ground truth: category = Hormones & Thyroid; Used For = Hyperthyroidism (Overactive
Thyroid) and Hypothyroidism (Underactive Thyroid).

Checks: nav drug page | answer has category + both conditions (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--7', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/levothyroxine"),
            f"navigated={navigated_to(t, '/drug/levothyroxine')}")
    j.check("answer_category", contains_all(fa, ["hormones", "thyroid"]), f"final={fa!r}")
    j.check("answer_used_for",
            contains_all(fa, ["hyperthyroidism", "hypothyroidism"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa,
        "Category: Hormones & Thyroid; Used For: Hyperthyroidism (Overactive Thyroid) and Hypothyroidism (Underactive Thyroid)",
        "What is levothyroxine's category label and which conditions are in its 'Used For' sidebar?")
    j.check("answer_details_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/drug/levothyroxine") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Hormones & Thyroid; Used For: Hyperthyroidism, Hypothyroidism",
            "the category kicker and Used For sidebar of the levothyroxine page")
        j.check("screenshot_shows_details", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
