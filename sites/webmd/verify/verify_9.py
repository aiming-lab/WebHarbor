#!/usr/bin/env python3
"""Deterministic verifier for WebMD--9.

Atrial Fibrillation condition page > the factor Xa inhibitor anticoagulant (Apixaban);
report its standard AFib dose and the three criteria for the reduced dose.
Ground truth: 5 mg twice daily; reduced to 2.5 mg twice daily with at least two of:
age 80+, body weight 60 kg or less, elevated creatinine.

Checks: nav condition + drug page | answer has 5 mg twice daily + 3 criteria (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--9', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/atrial-fibrillation"),
            f"navigated={navigated_to(t, '/condition/atrial-fibrillation')}")
    j.check("nav_apixaban", navigated_to(t, "/drug/apixaban"),
            f"navigated={navigated_to(t, '/drug/apixaban')}")
    j.check("answer_standard_dose",
            contains_all(fa, ["5 mg"]) and contains_any(fa, ["twice", "2x", "bid"]), f"final={fa!r}")
    j.check("answer_reduced_criteria",
            contains_all(fa, ["80", "60"]) and contains_any(fa, ["creatinine"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa,
        "5 mg twice daily; reduced dose criteria: age 80 or older, body weight 60 kg or less, elevated creatinine",
        "What is apixaban's standard atrial-fibrillation dose and the three reduced-dose patient criteria?")
    j.check("answer_dose_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/drug/apixaban") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s,
            "5 mg twice daily; age 80+, weight 60 kg or less, elevated creatinine",
            "the Dosage section of the apixaban page")
        j.check("screenshot_shows_dose", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
