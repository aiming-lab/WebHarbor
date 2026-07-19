#!/usr/bin/env python3
"""Deterministic verifier for WebMD--6.

Warfarin drug page; report the three antibiotics its interactions section names
as raising bleeding risk.
Ground truth: ciprofloxacin, azithromycin, amoxicillin.

Checks: nav drug page | answer names all three antibiotics (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--6', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_drug", navigated_to(t, "/drug/warfarin"),
            f"navigated={navigated_to(t, '/drug/warfarin')}")
    j.check("answer_names_three_antibiotics",
            contains_all(fa, ["ciprofloxacin", "azithromycin", "amoxicillin"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "ciprofloxacin, azithromycin, and amoxicillin",
        "Which three antibiotics does warfarin's interactions section name as raising bleeding risk?")
    j.check("answer_antibiotics_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/drug/warfarin") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "ciprofloxacin, azithromycin, amoxicillin",
            "the Interactions section of the warfarin page")
        j.check("screenshot_shows_interactions", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
