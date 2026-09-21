#!/usr/bin/env python3
"""Deterministic verifier for WebMD--8.

Migraine condition page > the related triptan (Sumatriptan) drug page; report the
maximum total dose in 24 hours and the minimum hours to wait before a second dose.
Ground truth: maximum 200 mg in 24 hours; wait at least 2 hours before a second dose.

Checks: nav condition + drug page | answer has 200 mg + 2 hours (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--8', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/migraine"),
            f"navigated={navigated_to(t, '/condition/migraine')}")
    j.check("nav_triptan_drug", navigated_to(t, "/drug/sumatriptan"),
            f"navigated={navigated_to(t, '/drug/sumatriptan')}")
    j.check("answer_max_dose", contains_number(fa, 200), f"final={fa!r}")
    j.check("answer_min_wait",
            contains_any(fa, ["2 hour", "2 hr", "2-hour", "two hour", "two hours"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Maximum 200 mg in 24 hours; second dose at least 2 hours after the first",
        "What is sumatriptan's maximum dose in 24 hours and the minimum hours before a second dose?")
    j.check("answer_dose_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/drug/sumatriptan") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Maximum 200 mg in 24 hours; second dose at least 2 hours after the first",
            "the Dosage section of the sumatriptan page")
        j.check("screenshot_shows_dose", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
