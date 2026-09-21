#!/usr/bin/env python3
"""Deterministic verifier for WebMD--4.

Search "Flomax" > the drug page (Tamsulosin); report the standard adult starting
dose and exactly when it should be taken relative to meals.
Ground truth: 0.4 mg once daily, taken about 30 minutes after the same meal each day.

Checks: nav drug page | answer has 0.4 mg + 30 minutes + after-meal (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--4', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/tamsulosin"),
            f"navigated={navigated_to(t, '/drug/tamsulosin')}")
    j.check("answer_dose", contains_all(fa, ["0.4"]) and contains_any(fa, ["mg"]), f"final={fa!r}")
    j.check("answer_timing",
            contains_any(fa, ["30 min", "30-min", "thirty min"]) and
            contains_any(fa, ["after a meal", "after the same meal", "after meals", "after the meal", "after eating"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "0.4 mg once daily, taken about 30 minutes after the same meal each day",
        "What is tamsulosin (Flomax)'s standard adult starting dose and when should it be taken relative to meals?")
    j.check("answer_dose_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/drug/tamsulosin") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "0.4 mg once daily, 30 minutes after the same meal",
            "the Dosage section of the tamsulosin page")
        j.check("screenshot_shows_dose", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
