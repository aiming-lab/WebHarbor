#!/usr/bin/env python3
"""Deterministic verifier for WebMD--10.

Gout condition page: report the diuretic its causes section names as a risk factor,
then open the related gout-attacks article and report who wrote it.
Ground truth: diuretic = hydrochlorothiazide; article author = Curtis Boone
(article: "Gout Attacks: Why They Happen at 3 A.M. ...").

Checks: nav condition + related article | answer names diuretic + author (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--10', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_condition", navigated_to(t, "/condition/gout"),
            f"navigated={navigated_to(t, '/condition/gout')}")
    j.check("nav_related_article", navigated_to(t, "/articles/gout-attacks-prevention"),
            f"navigated={navigated_to(t, '/articles/gout-attacks-prevention')}")
    j.check("answer_diuretic", contains_any(fa, ["hydrochlorothiazide"]), f"final={fa!r}")
    j.check("answer_author", contains_any(fa, ["boone"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Diuretic risk factor: hydrochlorothiazide; article written by Curtis Boone",
        "Which diuretic does gout's causes section name, and who wrote the linked gout-attacks article?")
    j.check("answer_details_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/articles/gout-attacks-prevention") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Written by Curtis Boone",
            "the byline of the gout-attacks article")
        j.check("screenshot_shows_author", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
