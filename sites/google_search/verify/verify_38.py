#!/usr/bin/env python3
"""Deterministic verifier for Google Search task Google Search--38.

Search for the next visible solar eclipse in North America and its expected date, and what about the one after that.

Ground truth (hardcoded; recorded from the served mirror pages of the running
container during the reviewer's real-Chromium audit; the catalog is fixed by
the seed DB and carries no wall-clock content):
    The mirror carries two coherent readings: (a) the NASA eclipse-decade
    page (2041-2050) lists the next TOTAL solar eclipse visible from North
    America on August 23, 2044 (path through Montana / North Dakota /
    Canada), and the one after that on August 12, 2045; (b) the timeanddate
    upcoming-eclipses list gives the next eclipse of any type visible from
    North America on 14 January 2029 (partial, Saros 151) with the next
    listed eclipse on 11 June 2029 (partial, Arctic). Either pair, taken
    consistently from one page, is accepted. (The lunar-eclipse pages are
    distractors.)
Source pages: eclipse.gsfc.nasa.gov/SEdecade/SEdecade2041

Checks (deterministic first; no LLM anywhere in this suite):
  nav: a solar-eclipse search | an eclipse listing page opened | answer:
  a mirror-consistent pair of dates (either reading)
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
    j = Judge('Google Search--38', a.no_llm)
    t, fa = grade_common(j, a)
    j.check("nav_task_search", searched_all_tokens(t, ["eclipse"]),
            "a /search?q= step carrying the task's key tokens")
    j.check("nav_answer_page", visited_any_page(t, ["task-038-", "SEdecade2041", "timeanddate.com/eclipse/list", "greatamericaneclipse"]),
            "an answer-bearing mirror page was opened")
    pair_a = re_any(fa, [r"\b2044\b"]) and re_any(fa, [r"august\s+23|23\s+august"]) \
        and re_any(fa, [r"\b2045\b"]) and re_any(fa, [r"august\s+12|12\s+august"])
    pair_b = re_any(fa, [r"january\s+14|14\s+january"]) and re_any(fa, [r"\b2029\b"]) \
        and re_any(fa, [r"june\s+11|11\s+june"])
    j.check("answer_eclipse_dates", pair_a or pair_b,
            f"final={fa[:200]!r}")
    j.emit()


if __name__ == "__main__":
    main()
