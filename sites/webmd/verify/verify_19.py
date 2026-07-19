#!/usr/bin/env python3
"""Deterministic verifier for WebMD--19.

Compare the atorvastatin and rosuvastatin drug pages: which one's 'Used For' list
links more conditions, and which conditions are on that drug's list but not the other's.
Ground truth: atorvastatin links more (4: Chronic Kidney Disease, Coronary Artery
Disease, High Cholesterol, Stroke) vs rosuvastatin (2: Coronary Artery Disease,
High Cholesterol). Atorvastatin-only: Chronic Kidney Disease and Stroke.

Checks: nav both drug pages | answer names atorvastatin + the two extra conditions (deterministic) | LLM+screenshot.
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
    j = Judge('WebMD--19', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_atorvastatin", navigated_to(t, "/drug/atorvastatin"),
            f"navigated={navigated_to(t, '/drug/atorvastatin')}")
    j.check("nav_rosuvastatin", navigated_to(t, "/drug/rosuvastatin"),
            f"navigated={navigated_to(t, '/drug/rosuvastatin')}")
    j.check("answer_names_winner", contains_any(fa, ["atorvastatin"]), f"final={fa!r}")
    j.check("answer_names_extra_conditions",
            contains_all(fa, ["chronic kidney disease", "stroke"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa,
        "Atorvastatin links more conditions (4 vs 2); conditions on atorvastatin but not rosuvastatin: Chronic Kidney Disease and Stroke",
        "Which statin's 'Used For' list links more conditions, and which conditions are unique to it vs the other?")
    j.check("answer_comparison_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/drug/atorvastatin") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Used For: Chronic Kidney Disease, Coronary Artery Disease, High Cholesterol, Stroke",
            "the atorvastatin 'Used For' sidebar")
        j.check("screenshot_shows_usedfor", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
