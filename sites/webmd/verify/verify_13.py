#!/usr/bin/env python3
"""Deterministic verifier for WebMD--13.

Symptom Checker: select Fever, Frequent urination, Painful urination; run the check;
report the top-ranked condition.
Ground truth: top condition = Urinary Tract Infection (UTI), matching all 3 symptoms.

Checks: nav symptom-checker | answer names UTI (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--13', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_symptom_checker", navigated_to(t, "/symptom-checker"),
            f"navigated={navigated_to(t, '/symptom-checker')}")
    j.check("answer_top_condition",
            contains_any(fa, ["urinary tract infection", "uti"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Top-ranked condition: Urinary Tract Infection (UTI)",
        "What is the top-ranked symptom-checker condition for fever, frequent urination, and painful urination?")
    j.check("answer_result_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/symptom-checker") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Urinary Tract Infection (UTI)",
            "the top result card on the symptom-checker results page")
        j.check("screenshot_shows_result", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
