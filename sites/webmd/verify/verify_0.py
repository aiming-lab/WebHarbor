#!/usr/bin/env python3
"""Deterministic verifier for WebMD--0.

Well-Being > Sleep > "How to Fall Asleep Faster"; report the medical reviewer.
Ground truth: reviewer = Miguel Santana, MD.

Checks: nav article page | answer names Santana (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--0', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/articles/fall-asleep-faster"),
            f"navigated={navigated_to(t, '/articles/fall-asleep-faster')}")
    j.check("answer_names_reviewer", contains_any(fa, ["santana"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa, "Miguel Santana, MD",
        "Who medically reviewed the WebMD article 'How to Fall Asleep Faster'?")
    j.check("answer_reviewer_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/articles/fall-asleep-faster") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Medically reviewed by Miguel Santana",
            "the byline of the fall-asleep-faster article")
        j.check("screenshot_shows_reviewer", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
