#!/usr/bin/env python3
"""Deterministic verifier for WebMD--2.

Diet & Weight Management > Food & Recipes > the article; report author + reviewer.
Ground truth: author = Sofia Andersson; reviewer = Danielle Hart, MD
(article: "Meal Prep Without Martyrdom: A 90-Minute Sunday System").

Checks: nav article page | answer names both (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--2', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/articles/meal-prep-90-minute-system"),
            f"navigated={navigated_to(t, '/articles/meal-prep-90-minute-system')}")
    j.check("answer_names_author_and_reviewer", contains_all(fa, ["andersson", "hart"]),
            f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Written by Sofia Andersson; medically reviewed by Danielle Hart, MD",
        "Who wrote and who medically reviewed the Food & Recipes meal-prep article?")
    j.check("answer_byline_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/articles/meal-prep-90-minute-system") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Written by Sofia Andersson; Medically reviewed by Danielle Hart",
            "the byline of the meal-prep article")
        j.check("screenshot_shows_byline", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
