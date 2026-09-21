#!/usr/bin/env python3
"""Deterministic verifier for WebMD--12.

Symptom Checker: select Dizziness, Heart palpitations, Fatigue, Shortness of breath;
run the check; report the top-ranked condition and how many selected symptoms matched.
Ground truth: top condition = Atrial Fibrillation, matching 4 of 4 symptoms.

Checks: nav symptom-checker | answer names AFib + 4 (deterministic) | LLM+screenshot anchored.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, navigated_to, navigated_any, final_answer, last_shot,
                        shot_after_url, contains_all, contains_any, contains_number,
                        answer_equals, date_present, resolve_db, saved_slugs_for,
                        saved_count_for, user_exists, password_hash_for, password_matches,
                        llm_text_match, llm_screenshot_shows, Judge, parse_args)

def main():
    a = parse_args()
    j = Judge('WebMD--12', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_symptom_checker", navigated_to(t, "/symptom-checker"),
            f"navigated={navigated_to(t, '/symptom-checker')}")
    j.check("answer_top_condition", contains_any(fa, ["atrial fibrillation", "afib", "a-fib"]),
            f"final={fa!r}")
    j.check("answer_match_count", contains_number(fa, 4), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Top-ranked condition: Atrial Fibrillation, matching 4 of the 4 selected symptoms",
        "What is the top-ranked symptom-checker condition and how many of the 4 selected symptoms did it match?")
    j.check("answer_result_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/symptom-checker") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Atrial Fibrillation — 4 of 4 symptoms match",
            "the top result card on the symptom-checker results page")
        j.check("screenshot_shows_result", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
