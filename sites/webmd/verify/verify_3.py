#!/usr/bin/env python3
"""Deterministic verifier for WebMD--3.

Search "how much water" > the hydration article; report author, medical reviewer,
and the topic (subcategory) it is filed under within its section.
Ground truth: author = Sofia Andersson; reviewer = Karen Shale, MD; topic = Healthy Living
(article: "Hydration: How Much Water You Actually Need", section Well-Being).

Checks: nav article page | answer names author+reviewer+topic (deterministic) | LLM+screenshot anchored.
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
    j = Judge('WebMD--3', a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)
    j.check("nav_article", navigated_to(t, "/articles/hydration-how-much-water"),
            f"navigated={navigated_to(t, '/articles/hydration-how-much-water')}")
    j.check("answer_author_reviewer_topic",
            contains_all(fa, ["andersson", "shale", "healthy living"]), f"final={fa!r}")
    ok, ev = llm_text_match(fa,
        "Written by Sofia Andersson; medically reviewed by Karen Shale, MD; filed under the Healthy Living topic",
        "Who wrote the hydration article, who reviewed it, and which topic is it filed under?")
    j.check("answer_details_llm", ok, ev, llm=True)
    s = shot_after_url(t, "/articles/hydration-how-much-water") or last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "Sofia Andersson, Karen Shale, Healthy Living",
            "the byline and topic kicker of the hydration article")
        j.check("screenshot_shows_details", ok, ev, llm=True)
    j.emit()

if __name__ == "__main__":
    main()
