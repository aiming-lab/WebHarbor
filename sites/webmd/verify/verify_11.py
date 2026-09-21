#!/usr/bin/env python3
"""Deterministic verifier for WebMD--11.

Vertigo (BPPV) condition page; report the repositioning maneuver its treatments
section says cures most cases and the anti-nausea medicine for short-term relief.
Ground truth: maneuver = Epley maneuver; anti-nausea medicine = ondansetron.

Checks: nav condition page | answer names Epley + ondansetron (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--11', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/vertigo-bppv"),
            f"navigated={navigated_to(t, '/condition/vertigo-bppv')}")
    j.check("answer_maneuver", contains_any(fa, ["epley"]), f"final={fa!r}")
    j.check("answer_antinausea", contains_any(fa, ["ondansetron"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Epley maneuver; anti-nausea medicine ondansetron",
        "Which repositioning maneuver cures most BPPV cases and which anti-nausea medicine is named for short-term relief?")
    j.check("answer_details_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/condition/vertigo-bppv") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Epley maneuver; ondansetron",
            "the Treatments section of the Vertigo (BPPV) page")
        j.check("screenshot_shows_treatments", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
