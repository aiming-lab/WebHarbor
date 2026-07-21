#!/usr/bin/env python3
"""Deterministic verifier for Target--0.

Find the returns Help topic and report the opened-beauty window and the
Target-owned-brand window.

Ground truth (frozen here, never read from tasks.jsonl):
  Support article 'returns-and-exchanges' body:
    "Most items can be returned within 90 days. Target owned brands carry a
     one-year return window with a receipt. Opened beauty items can be
     returned within 60 days."
  -> opened beauty = 60 days; Target owned brands = one year.

The task deliberately does NOT ask for the 90-day figure: that sentence is the
article's summary, which the search results page prints verbatim, so it is
answerable without ever opening the article. The 60-day and one-year facts
appear only in the body.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (load_run, final_answer, last_shot, visited_product, navigated_to,
                        has_number, contains_any, contains_all, resolve_db,
                        db_unchanged_for, llm_text_match, llm_screenshot_shows,
                        Judge, parse_args)


def main():
    a = parse_args()
    j = Judge("Target--0", a.no_llm)
    t = load_run(a.run_dir)
    fa = final_answer(t)

    j.check("opened_returns_article", navigated_to(t, "/support/returns-and-exchanges"),
            f"visited={navigated_to(t, '/support/returns-and-exchanges')}")
    beauty_ok = has_number(fa, 60)
    # A year is equally correct written as "one year", "12 months" or "365 days".
    # Only accepting the words made a correct "365 days" answer fail.
    year_ok = (contains_any(fa, ["one year", "one-year", "1 year", "1-year",
                                 "a year", "12 month", "twelve month"])
               or has_number(fa, 365) or has_number(fa, 12))
    j.check("answer_states_opened_beauty_window", beauty_ok, f"final={fa!r}")
    j.check("answer_states_owned_brand_window", year_ok, f"final={fa!r}")

    # The article's summary — "Most items can be returned within 90 days" — is
    # printed verbatim on the search results page. An answer built only from it
    # never opened the article, so require BOTH body facts explicitly rather
    # than relying on the 90 check to catch it.
    j.check("not_only_the_summary_fact", beauty_ok and year_ok,
            f"answer must carry both body facts, not just the 90-day summary: final={fa!r}")

    initial = resolve_db(a.initial_db, a.container, "instance_seed")
    after = resolve_db(a.after_db, a.container, "instance")
    unchanged = db_unchanged_for(initial, after, "alice.j@test.com")
    j.check("read_only_task_left_db_alone", unchanged is True,
            f"db_unchanged={unchanged}")

    ok, ev = llm_text_match(fa, "opened beauty items: 60 days; Target owned brands: one year with a receipt",
        "How long to return an opened beauty item, and what is the Target owned brand window?")
    j.check("answer_matches_ground_truth", ok, ev, llm=True)

    s = last_shot(t)
    if s:
        ok, ev = llm_screenshot_shows(s, "a 60 day window for opened beauty items and a one-year window for Target owned brands",
            "the returns and exchanges article body")
        j.check("screenshot_shows_answer", ok, ev, llm=True)
    else:
        j.check("screenshot_shows_answer", False, "no screenshots in run")

    j.emit()


if __name__ == "__main__":
    main()
