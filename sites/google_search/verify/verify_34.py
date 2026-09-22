#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--34.

Determine the distance from Earth to Mars as of today's date.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror's Mars-distance pages agree on the current distance: Mars
    sits roughly 217 million kilometers from Earth (about twelve
    light-minutes); timeanddate gives 216.4 million km; the next opposition
    is at approximately 99 million kilometers. (The pages carry a frozen
    'today' value — see the audit note in REPORT.md on the run-date wording.)
Source pages: www.space.com/mars-distance-from-earth-today.html, jpl.nasa.gov, timeanddate

Checks (deterministic first; no LLM anywhere in this suite):
  nav: an Earth-Mars distance search | a Mars distance page opened | answer:
  the current distance as the page reports it
Input/Output: see verify_lib.parse_args / verify_lib.Judge.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lib import (grade_common, Judge, parse_args, searched_all_tokens,
                        visited_any_page, navigated_to, contains_all, contains_any,
                        re_any, re_count, number_claim, date_in, name_in, count_names,
                        order_by_first_mention)


def main():
    a = parse_args()
    j = Judge('Google Search--34', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["mars", "distance"]) or searched_all_tokens(t, ["earth", "mars"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-034-", "mars-distance-from-earth-today", "mars-distance-today", "night-sky", "planets/mars"]),
            "an answer-bearing mirror page was opened")
    j.check("answer_current_distance", re_any(fa, [r"\b217\b[^\d]{0,25}(million|km|kilometer)", r"\b216\.4\b[^\d]{0,25}(million|km|kilometer)", r"twelve light-min"]),
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
